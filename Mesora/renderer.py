"""Session graphics. All groups belong to the manager, never to a command."""
import math
import uuid
import adsk.core
import adsk.fusion
from .dimensions.fusion_geometry import measure, point, minimum_distance, angle_geometry
from .dimensions.layout import add, sub, mul, dot, cross, unit, basis, readable_axes, find_clear_placement, clear_intervals, face_axis
from .dimensions.label_layout import choose_caption, projected_caption_size, projection_scale

_LABELS = {}
_ANGLES = {}
_CAPTIONS = {}
OWNERSHIP_PREFIX = '4FusionLab.Mesora.89072f8c-cdca-48bf-8a2a-440c9ae898e6.graphics.v1:'


def xyz(p): return (p.x, p.y, p.z)
def p3(p): return adsk.core.Point3D.create(*p)


def forget(group):
    _LABELS.pop(id(group), None)
    _ANGLES.pop(id(group), None)
    _CAPTIONS.pop(id(group), None)


def arrange_labels(groups, camera, viewport):
    """Pack one visible batch of captions in screen space without moving dimensions.

    Each caption remains in its own model plane. Extra leader lines connect a
    displaced caption to its original anchor. Keep the previous world position
    while its text bounds remain clear. When reflow is required, search from
    the original attachment so repeated orbit cannot accumulate displacement.
    """
    occupied = []
    viewport_width, viewport_height = getattr(viewport, 'width', None), getattr(viewport, 'height', None)
    bounds = (0, 0, viewport_width, viewport_height) if viewport_width and viewport_height else None
    target = getattr(camera, 'target', None)
    projected_target = viewport.modelToViewSpace(target) if target is not None else None
    pixel_scale = projection_scale(viewport_width, viewport_height,
        (projected_target.x, projected_target.y) if projected_target is not None else None)
    def project(value):
        point = viewport.modelToViewSpace(p3(value))
        return point.x/pixel_scale, point.y/pixel_scale
    for group in groups:
        key = id(group)
        if not group.isValid or not getattr(group, 'isVisible', True) or key not in _LABELS:
            continue
        saved = _CAPTIONS.get(key)
        base = saved['base'] if saved else _LABELS[key][1]
        if saved is None:
            saved = {'base': base, 'leader': None}
            _CAPTIONS[key] = saved
        saved['base'] = base
        text, _, xaxis, yaxis, size, previous, face_camera = _LABELS[key]
        orient_text(group, camera)
        signature = _LABELS[key][5]
        text_x, text_y = signature[:3], signature[3:6]
        origin = project(base)
        tx, ty = project(add(base, text_x)), project(add(base, text_y))
        width, height = projected_caption_size(max(float(text.width)*16/size, 16), 20,
            (tx[0]-origin[0], tx[1]-origin[1]), (ty[0]-origin[0], ty[1]-origin[1]))
        px, py = project(add(base, xaxis)), project(add(base, yaxis))
        dx, dy = (px[0]-origin[0], px[1]-origin[1]), (py[0]-origin[0], py[1]-origin[1])
        determinant = dx[0]*dy[1]-dx[1]*dy[0]
        scale_product = math.hypot(*dx)*math.hypot(*dy)
        well_conditioned = scale_product > 1e-12 and abs(determinant)/scale_product >= .08

        def candidates():
            yield origin, base
            # Lazy candidates keep ordinary, non-overlapping orbit inexpensive.
            for ring in range(1, 49):
                if well_conditioned:
                    displacements = ((0, -ring*(height+12)), (0, ring*(height+12)),
                                     (-ring*(width+12), 0), (ring*(width+12), 0),
                                     (-ring*(width+12), -ring*(height+12)),
                                     (ring*(width+12), -ring*(height+12)),
                                     (-ring*(width+12), ring*(height+12)),
                                     (ring*(width+12), ring*(height+12)))
                    for sx, sy in displacements:
                        a = (sx*dy[1]-sy*dy[0])/determinant
                        b = (dx[0]*sy-dx[1]*sx)/determinant
                        candidate = add(base, add(mul(xaxis, a), mul(yaxis, b)))
                        yield project(candidate), candidate
                else:
                    # An edge-on plane still permits travel on its visible axis.
                    axis, screen = (xaxis, dx) if math.hypot(*dx) >= math.hypot(*dy) else (yaxis, dy)
                    length = math.hypot(*screen)
                    if length < 1e-8:
                        break
                    step = ring*(width+height+16)/length
                    for sign in (-1, 1):
                        candidate = add(base, mul(axis, sign*step))
                        yield project(candidate), candidate

        placed = saved.get('placed')
        if placed is not None:
            try:
                # Preserve world placement while the actual text bounds remain
                # clear. Removing only the extra packing padding is hysteresis:
                # a small camera motion must not chase the 5px reserve margin.
                anchor, rect = choose_caption(width, height, occupied,
                    [(project(placed), placed)], padding=0, bounds=bounds)
            except ValueError:
                anchor, rect = choose_caption(width, height, occupied, candidates(), bounds=bounds)
        else:
            anchor, rect = choose_caption(width, height, occupied, candidates(), bounds=bounds)
        saved['placed'] = anchor
        occupied.append(rect)
        _LABELS[key] = (text, anchor, xaxis, yaxis, size, signature, face_camera)
        orient_text(group, camera)
        moved = math.dist(base, anchor) > 1e-9
        leader = saved['leader']
        if moved:
            coordinates = adsk.fusion.CustomGraphicsCoordinates.create([v for point in (base, anchor) for v in point])
            if leader is None:
                leader = group.addLines(coordinates, [], False)
                if not leader:
                    raise RuntimeError('Failed to connect displaced caption')
                leader.color = text.color
                leader.weight = 1
                leader.isSelectable = False
                saved['leader'] = leader
            else:
                leader.coordinates = coordinates
            leader.isVisible = True
        elif leader is not None:
            leader.isVisible = False


def owned_groups(design, keep=()):
    """Find tagged graphics, including fresh wrappers restored by Fusion Undo.

    All Mesora graphics are root groups. Do not inspect/delete another add-in's
    groups or infer ownership from text, selection names, or empty IDs.
    """
    groups = design.rootComponent.customGraphicsGroups
    snapshot = [groups.item(index) for index in range(groups.count)]
    return [group for group in snapshot
            if group.isValid and group.id.startswith(OWNERSHIP_PREFIX)
            and not any(group == retained for retained in keep)]


def erase_owned(design, keep=()):
    """Delete owned groups; return failed groups so the caller retains ownership."""
    failed = []
    for group in owned_groups(design, keep):
        try:
            if group.deleteMe():
                forget(group)
            else:
                failed.append(group)
        except Exception:
            failed.append(group)
    return failed


def angle_layout(apex, x, y, value, offset, camera, viewport=None):
    """Keep the projected arc large enough for its caption, even on short edges."""
    steps = max(16, int(math.ceil(value / (math.pi / 48))))
    rays = [add(mul(x, math.cos(value*i/steps)), mul(y, math.sin(value*i/steps))) for i in range(steps+1)]
    radius = max(getattr(camera, 'viewExtents', 1) * .08, .5)
    if viewport is not None:
        def project(p):
            q = viewport.modelToViewSpace(p3(p))
            return q.x, q.y
        origin = project(apex)
        for _ in range(4):
            screen = [project(add(apex, mul(ray, radius))) for ray in rays]
            arc = sum(math.dist(a,b) for a,b in zip(screen, screen[1:]))
            extent = max(math.dist(origin,p) for p in screen)
            chord = math.dist(screen[0], screen[-1])
            factor = max(90/max(extent,1e-6), 140/max(arc,1e-6), 80/max(chord,1e-6))
            if abs(factor-1) < .03:
                break
            radius *= min(4, max(.25, factor))
    radius += offset
    if radius <= 0:
        raise ValueError('Angle offset makes the arc radius non-positive')
    points = [add(apex, mul(ray, radius)) for ray in rays]
    segments = [(apex, points[0]), (apex, points[-1])] + list(zip(points, points[1:]))
    return segments, points[steps//2]


def orient_text(group, camera):
    data = _LABELS.get(id(group))
    if data is None or not group.isValid:
        return
    text, anchor, axis_x, axis_y, size, previous, face_camera = data
    # Readability belongs to the model attachment, not an automatic caption shift.
    # Orbit/zoom must not resize angular geometry or move its attachment point.
    base = _CAPTIONS.get(id(group), {}).get('base', anchor)
    eye_direction = sub(xyz(camera.eye), base)
    if face_camera:
        z = unit(eye_direction)
        x = unit(cross(mul(z, -1), xyz(camera.upVector)))
        y = unit(cross(z, x))
    else:
        previous_normal = previous[6:9] if previous else None
        x, y, z = readable_axes(axis_x, axis_y, eye_direction, xyz(camera.upVector), previous_normal)
    signature = tuple(round(v, 7) for vector in (x, y, z, anchor) for v in vector)
    if signature == previous:
        return
    origin = add(add(anchor, mul(x, -text.width / 2)), mul(y, size * .25))
    matrix = adsk.core.Matrix3D.create()
    if not matrix.setWithCoordinateSystem(p3(origin), adsk.core.Vector3D.create(*x), adsk.core.Vector3D.create(*y), adsk.core.Vector3D.create(*z)):
        raise RuntimeError('Failed to orient dimension text')
    text.transform = matrix
    _LABELS[id(group)] = (text, anchor, axis_x, axis_y, size, signature, face_camera)


def perpendicular(direction, view):
    try: return unit(cross(direction, view))
    except ValueError:
        axis = min(((1,0,0), (0,1,0), (0,0,1)), key=lambda a: abs(dot(a, direction)))
        return unit(cross(direction, axis))


def edge_plane(edge, midpoint):
    """Find a planar face and its local outside, respecting inner loops."""
    planes = []
    start, end = line_endpoints(edge)
    direction = unit(sub(end, start))
    edge_length = sum((b - a) ** 2 for a, b in zip(start, end)) ** .5
    for face in edge.faces:
        geometry = face.geometry
        if geometry.objectType == 'adsk::core::Plane':
            normal = xyz(geometry.normal)
            _, candidate, _ = basis(direction, normal)
            # A face's pointOnFace can lie across a hole or concavity. Probe
            # locally on both sides at several positions along the edge.
            plus_inside = minus_inside = 0
            step = max(min(edge_length * .002, .02), .0001)
            for fraction in (.25, .5, .75):
                sample = add(start, mul(sub(end, start), fraction))
                for factor in (1, 4):
                    p_plus = p3(add(sample, mul(candidate, step * factor)))
                    p_minus = p3(add(sample, mul(candidate, -step * factor)))
                    try:
                        plus = face.isPointOnFace(p_plus)
                        minus = face.isPointOnFace(p_minus)
                    except RuntimeError:
                        continue
                    if plus and not minus: plus_inside += 1
                    elif minus and not plus: minus_inside += 1
            confidence = abs(plus_inside - minus_inside)
            if confidence:
                outward = mul(candidate, -1 if plus_inside > minus_inside else 1)
            else:
                outward = sub(midpoint, xyz(face.pointOnFace))
            # Prefer a face with unambiguous local evidence, then a stable
            # model-axis preference; inner-loop faces take precedence when
            # local evidence exists, so holes and slots offset into the void.
            inner = any(not loop.isOuter and any(loop_edge == edge for loop_edge in loop.edges)
                        for loop in getattr(face, 'loops', []))
            key = (bool(inner and confidence), confidence, abs(normal[2]), abs(normal[1]), abs(normal[0]))
            planes.append((key, normal, outward))
    if not planes:
        return None, None
    _, normal, outward = max(planes, key=lambda candidate: candidate[0])
    return normal, outward



def visible_solids(root):
    bodies = [body for body in root.bRepBodies if body.isVisible and body.isSolid]
    for occurrence in root.allOccurrences:
        if occurrence.isVisible:
            bodies.extend(body for body in occurrence.bRepBodies if body.isVisible and body.isSolid)
    return bodies


def adjacent_plane_normals(edge):
    return [unit(xyz(face.geometry.normal)) for face in edge.faces
            if face.geometry.objectType == 'adsk::core::Plane']


def segment_is_clear(root, bodies, start, end, tolerance):
    delta = sub(end, start)
    length = math.sqrt(dot(delta, delta))
    if length <= tolerance:
        return False
    direction = unit(delta)
    # Intersections alone miss a segment wholly inside a body. Unknown and
    # boundary states are treated as blocked, not silently accepted.
    outside = adsk.fusion.PointContainment.PointOutsidePointContainment
    for fraction in (.02, .25, .5, .75, .98):
        sample = p3(add(start, mul(delta, fraction)))
        for body in bodies:
            if body.pointContainment(sample) != outside:
                return False
    hits = adsk.core.ObjectCollection.create()
    found = root.findBRepUsingRay(p3(start), adsk.core.Vector3D.create(*direction),
                                 adsk.fusion.BRepEntityTypes.BRepFaceEntityType,
                                 tolerance, True, hits)
    if found is None or found.count != hits.count:
        raise ValueError('Cannot verify dimension clearance')
    for hit in hits:
        distance = dot(sub(xyz(hit), start), direction)
        if tolerance < distance < length - tolerance:
            return False
    return True


def edge_clearance(root, edge, a, b, desired, preferred):
    bodies = visible_solids(root)
    tolerance = max(min(desired * .001, .0001), 1e-6)
    direction = unit(sub(b, a))
    def is_clear(side, offset):
        q1, q2 = add(a, mul(side, offset)), add(b, mul(side, offset))
        segments = [(a, add(q1, mul(side, offset*.12))),
                    (b, add(q2, mul(side, offset*.12))), (q1, q2)]
        arrow = min(math.sqrt(dot(sub(b, a), sub(b, a)))*.08, offset*.45)
        for tip, d in ((q1, direction), (q2, mul(direction, -1))):
            back = add(tip, mul(d, arrow))
            segments.extend((tip, add(back, mul(side, sign*arrow*.35))) for sign in (-1, 1))
        return all(segment_is_clear(root, bodies, p, q, tolerance) for p, q in segments)
    return find_clear_placement(direction, preferred, desired, is_clear,
                                adjacent_plane_normals(edge))


def distance_clearance(root, a, b, desired, preferred):
    """Try to place the distance line outside visible solids."""
    bodies = visible_solids(root)
    if not bodies:
        return preferred, desired, None
    tolerance = max(min(desired * .001, .0001), 1e-6)
    q1, q2 = add(a, mul(preferred, desired)), add(b, mul(preferred, desired))
    if all(segment_is_clear(root, bodies, start, end, tolerance) for start, end in (
        (q1, q2), (a, add(q1, mul(preferred, desired*.12))),
        (b, add(q2, mul(preferred, desired*.12))))):
        return preferred, desired, None
    diagonals = []
    for body in bodies:
        bounds = body.boundingBox
        delta = sub(xyz(bounds.maxPoint), xyz(bounds.minPoint))
        diagonals.append(math.sqrt(dot(delta, delta)))
    maximum = max([desired] + [length * .55 for length in diagonals])
    candidate = desired
    while candidate < maximum:
        try:
            return clipped_edge_layout(root, a, b, candidate, preferred, min_offset=desired)
        except ValueError as exc:
            if str(exc) != 'No sufficiently visible dimension placement found near this edge':
                raise
        candidate *= 2
    return clipped_edge_layout(root, a, b, maximum, preferred, min_offset=desired)


def visible_segments(root, bodies, start, end, tolerance):
    delta = sub(end, start)
    length = math.sqrt(dot(delta, delta))
    if length <= tolerance * 4:
        return []
    direction = unit(delta)
    hits = adsk.core.ObjectCollection.create()
    found = root.findBRepUsingRay(p3(start), adsk.core.Vector3D.create(*direction),
                                 adsk.fusion.BRepEntityTypes.BRepFaceEntityType,
                                 tolerance, True, hits)
    if found is None or found.count != hits.count:
        raise ValueError('Cannot verify dimension clearance')
    distances = [dot(sub(xyz(hit), start), direction) for hit in hits]
    def clear(lo, hi):
        return segment_is_clear(root, bodies, add(start, mul(direction, lo)),
                                add(start, mul(direction, hi)), tolerance)
    return [(add(start, mul(direction, lo)), add(start, mul(direction, hi)))
            for lo, hi in clear_intervals(length, distances, tolerance * 4, clear)]


def clipped_edge_layout(root, a, b, desired, preferred, surface_normals=(), min_offset=0):
    """Find a legible dimension whose obscured portions can be omitted."""
    bodies = visible_solids(root)
    tolerance = max(min(desired * .001, .0001), 1e-6)
    direction, side, normal = basis(sub(b, a), outward=preferred)
    # basis() without a normal does not necessarily recover preferred.
    side = unit(sub(preferred, mul(direction, dot(preferred, direction))))
    normal = unit(cross(direction, side))
    length = math.sqrt(dot(sub(b, a), sub(b, a)))
    best = None
    for fraction in (1, .5, .25):
        off = desired * fraction
        if off + 1e-12 < min_offset:
            continue
        for i in range(24):
            angle = i * math.pi / 12
            v = add(mul(side, math.cos(angle)), mul(normal, math.sin(angle)))
            q1, q2 = add(a, mul(v, off)), add(b, mul(v, off))
            line = visible_segments(root, bodies, q1, q2, tolerance)
            line_length = sum(math.sqrt(dot(sub(y, x), sub(y, x))) for x, y in line)
            middle = mul(add(q1, q2), .5)
            # The label must sit on a visible section, with most of the
            # dimension line available to convey the measurement.
            if line_length < length * .75 or not any(
                dot(sub(middle, x), sub(middle, y)) <= 0 for x, y in line
            ):
                continue
            legs = []
            leg_parts = []
            for p, q in ((a, q1), (b, q2)):
                parts = visible_segments(root, bodies, p,
                                         add(q, mul(v, off*.12)), tolerance)
                leg_parts.append(parts)
                legs.extend(parts)
            arrow = min(length*.08, off*.45)
            arrows = []
            for tip, d in ((q1, unit(sub(b, a))), (q2, unit(sub(a, b)))):
                back = add(tip, mul(d, arrow))
                for sign in (-1, 1):
                    arrows.extend(visible_segments(root, bodies, tip, add(back, mul(v, sign*arrow*.35)), tolerance))
            if not arrows:
                continue
            leg_length = sum(math.sqrt(dot(sub(y, x), sub(y, x))) for x, y in legs)
            edge_middle = mul(add(a, b), .5)
            path_clear = segment_is_clear(root, bodies,
                                          add(edge_middle, mul(v, off*.08)),
                                          add(edge_middle, mul(v, off*.98)), tolerance)
            attached = sum(bool(parts) and math.sqrt(dot(sub(parts[0][0], p), sub(parts[0][0], p))) <= tolerance * 4
                           for parts, p in zip(leg_parts, (a, b)))
            separation = min((abs(dot(v, n)) for n in surface_normals), default=0)
            score = (path_clear, attached, fraction, round(separation, 8), line_length / length, leg_length / off, len(arrows), -i)
            if best is None or score > best[0]:
                best = (score, v, off, legs + line + arrows)
    if best is None:
        raise ValueError('No sufficiently visible dimension placement found near this edge')
    return best[1:]


def edge_mid(edge):
    ev = edge.evaluator if edge.objectType == 'adsk::fusion::BRepEdge' else edge.worldGeometry.evaluator
    ok, lo, hi = ev.getParameterExtents()
    if not ok: raise ValueError('Cannot obtain edge range')
    ok, p = ev.getPointAtParameter((lo + hi)/2)
    if not ok: raise ValueError('Cannot evaluate edge')
    return xyz(p)


def line_endpoints(edge):
    ev = edge.evaluator
    ok, a, b = ev.getEndPoints()
    if not ok: raise ValueError('Cannot evaluate edge endpoints')
    return xyz(a), xyz(b)


def round_geometry(entity):
    typ = entity.objectType
    if typ == 'adsk::fusion::BRepFace':
        geo = entity.geometry
        anchor = xyz(entity.pointOnFace)
        axis, origin = unit(xyz(geo.axis)), xyz(geo.origin)
        center = add(origin, mul(axis, dot(sub(anchor, origin), axis)))
        return center, anchor, axis
    if typ == 'adsk::fusion::BRepEdge':
        return xyz(entity.geometry.center), edge_mid(entity), xyz(entity.geometry.normal)
    geo = entity.worldGeometry
    if typ == 'adsk::fusion::SketchArc':
        return xyz(geo.center), xyz(geo.startPoint), xyz(geo.normal)
    center = xyz(geo.center)
    normal = unit(xyz(geo.normal))
    direction = perpendicular(normal, (0,0,1))
    return center, add(center, mul(direction, geo.radius)), normal


def cached_layout(cache, ident, signature, calculate):
    """Reuse clearance work only within the owning command's lifetime."""
    if cache is None or ident is None:
        return calculate()
    entry = cache.get(ident)
    if entry is not None and entry[0] == signature:
        return entry[1]
    result = calculate()
    cache[ident] = (signature, result)
    return result


def obstacle_signature(root):
    # Internal cuts can change clearance without changing a body's bounds.
    return tuple((body, getattr(body, 'revisionId', None),
                  xyz(body.boundingBox.minPoint), xyz(body.boundingBox.maxPoint))
                 for body in visible_solids(root))


def render(design, kind, entities, camera, ident=None, offset=0, layout_cache=None, obstacles=None):
    value = measure(kind, entities)
    group = design.rootComponent.customGraphicsGroups.add()
    if group is None: raise RuntimeError('Failed to create graphics group')
    try:
        # Fusion Undo can recreate groups with wrappers the State never saw.
        # A product-specific ID lets refresh/save/stop reclaim only our groups.
        group.id = OWNERSHIP_PREFIX + uuid.uuid4().hex
        # Informational annotations must never mask selectable model geometry.
        # Disable selection at the group level, including its line children.
        group.isChildrenSelectable = False
        group.isSelectable = False
        segments = []
        face_camera = False
        if kind == 'angle':
            value, (first, apex, last) = angle_geometry(*entities)
            v1, v2 = sub(first, apex), sub(last, apex)
            l1, l2 = math.sqrt(dot(v1, v1)), math.sqrt(dot(v2, v2))
            if min(l1, l2) < 1e-9:
                raise ValueError('Cannot determine angle display directions')
            x = unit(v1)
            perpendicular_part = sub(unit(v2), mul(x, dot(unit(v2), x)))
            if dot(perpendicular_part, perpendicular_part) < 1e-16:
                raise ValueError('Parallel objects do not define a visible angle arc')
            y = unit(perpendicular_part)
            viewport = adsk.core.Application.get().activeViewport if hasattr(adsk.core, 'Application') else None
            segments, label = angle_layout(apex, x, y, value, offset, camera, viewport)
            tangent = add(mul(x, -math.sin(value / 2)), mul(y, math.cos(value / 2)))
            text_x, text_y, text_z = basis(tangent, cross(x, y))
            prefix = ''
        elif kind == 'distance' and value <= 1e-9:
            _, a, _ = minimum_distance(entities[0], entities[1])
            eye = unit(sub(xyz(camera.eye), a))
            text_x = unit(cross(mul(eye, -1), xyz(camera.upVector)))
            text_y = unit(cross(eye, text_x))
            text_z = unit(cross(text_x, text_y))
            segments = [(add(a, mul(text_x, -.05)), add(a, mul(text_x, .05))),
                        (add(a, mul(text_y, -.05)), add(a, mul(text_y, .05)))]
            label, prefix = add(a, mul(text_x, offset)), 'Min = '
            if offset: segments.append((a, label))
        elif kind == 'distance' or (kind == 'edge_length' and entities[0].objectType == 'adsk::fusion::BRepEdge' and entities[0].geometry.objectType == 'adsk::core::Line3D'):
            a, b = minimum_distance(entities[0], entities[1])[1:] if kind == 'distance' else line_endpoints(entities[0])
            direction = unit(sub(b, a))
            normal, outward = edge_plane(entities[0], mul(add(a, b), .5)) if kind == 'edge_length' else (None, None)
            text_x, text_y, text_z = basis(direction, normal, outward)
            side = text_y
            off = max(value * .2, .5, getattr(camera, 'viewExtents', 0.0) * .03) if kind == 'distance' else max(value * .06, .05)
            clipped_segments = None
            def calculate_layout():
                local_side, local_off, clipped = side, off, None
                if kind == 'edge_length':
                    try:
                        local_side, local_off = edge_clearance(design.rootComponent, entities[0], a, b, local_off, local_side)
                    except ValueError as exc:
                        if str(exc) != 'No clear dimension placement found near this edge':
                            raise
                        local_side, local_off, clipped = clipped_edge_layout(design.rootComponent, a, b, local_off, local_side, adjacent_plane_normals(entities[0]))
                elif any(getattr(e, 'objectType', '') in ('adsk::fusion::BRepFace', 'adsk::fusion::BRepEdge') for e in entities):
                    local_side, local_off, clipped = distance_clearance(design.rootComponent, a, b, local_off, local_side)
                if offset:
                    local_off = max(local_off + offset, 1e-6)
                    if clipped is not None:
                        local_side, local_off, clipped = clipped_edge_layout(design.rootComponent, a, b, local_off, local_side, adjacent_plane_normals(entities[0]) if kind == 'edge_length' else (), min_offset=local_off)
                return local_side, local_off, clipped
            # Visibility can change while the command is open. Include the
            # visible solids and their bounds so a changed obstacle is checked
            # again; the cache never survives the command itself.
            if layout_cache is not None and obstacles is None:
                obstacles = obstacle_signature(design.rootComponent)
            signature = (kind, tuple(entities), a, b, side, off, offset, obstacles)
            side, off, clipped_segments = cached_layout(layout_cache, ident, signature, calculate_layout)
            text_y = side
            text_z = unit(cross(text_x, text_y))
            q1, q2 = add(a, mul(side, off)), add(b, mul(side, off))
            if clipped_segments is not None:
                segments.extend(clipped_segments)
            else:
                segments += [(a, add(q1,mul(side,off*.12))), (b, add(q2,mul(side,off*.12))), (q1,q2)]
                arrow = min(value*.08, off*.45)
                for tip, d in ((q1,direction),(q2,mul(direction,-1))):
                    back = add(tip,mul(d,arrow)); segments.extend([(tip,add(back,mul(side,arrow*.35))), (tip,add(back,mul(side,-arrow*.35)))])
            label = mul(add(q1,q2), .5)
            prefix = 'Min = ' if kind == 'distance' else ''
        elif kind in ('area', 'perimeter'):
            face = entities[0]
            surface_point = face.pointOnFace
            anchor = xyz(surface_point)
            ok, surface_normal = face.evaluator.getNormalAtPoint(surface_point)
            if not ok or not surface_normal:
                raise ValueError('Cannot determine face normal')
            normal = unit(xyz(surface_normal))
            # Pick a direction in the tangent plane that reads horizontally in
            # the current view; keep it model-fixed after creation.
            eye = unit(sub(xyz(camera.eye), anchor))
            screen_right = unit(cross(mul(eye, -1), xyz(camera.upVector)))
            direction = face_axis(normal, screen_right)
            text_x, text_y, text_z = basis(direction, normal)
            scale = max((value ** .5 if kind == 'area' else value) * .05, .1)
            label = add(anchor, mul(text_x, scale + offset))
            segments.append((anchor, label))
            prefix = 'A = ' if kind == 'area' else 'P = '
        else:
            if kind == 'edge_length':
                anchor = edge_mid(entities[0])
                geometry = entities[0].geometry if entities[0].objectType == 'adsk::fusion::BRepEdge' else entities[0].worldGeometry
                if geometry.objectType in ('adsk::core::Circle3D', 'adsk::core::Arc3D'):
                    direction = unit(sub(anchor, xyz(geometry.center)))
                    text_x, text_y, text_z = basis(direction, xyz(geometry.normal))
                else:
                    text_x, text_y, text_z = basis((1, 0, 0))
                direction = text_x
                scale = max(value*.12,.1) + offset; end = add(anchor,mul(direction,scale)); prefix = 'L = '
                segments.append((anchor,end)); label=end
            else:
                center, anchor, normal = round_geometry(entities[0]); direction = unit(sub(anchor,center)); text_x, text_y, text_z = basis(direction, normal)
                side = text_y
                # Extending beyond a concave edge can put the label inside the
                # solid. Keep the radius annotation on the selected side of it.
                start = center if kind == 'radius' else add(center, mul(direction, -value/2))
                segments.append((start, anchor))
                arrow = max(value*.07,.03); back = add(anchor,mul(direction,-arrow))
                segments.extend([(anchor,add(back,mul(side,arrow*.35))), (anchor,add(back,mul(side,-arrow*.35)))])
                # Keep the radius line aimed at the centre while moving its
                # label off the small, often edge-on cylindrical face.
                view_extent = getattr(camera, 'viewExtents', 0.0)
                extension = max(value * .5, view_extent * .04, .02)
                travel = extension + offset
                if travel <= 0:
                    raise ValueError('Offset moves the radial label past its attachment point')
                end = add(anchor, mul(direction, travel))
                body = getattr(entities[0], 'body', None)
                if body is not None:
                    outside = adsk.fusion.PointContainment.PointOutsidePointContainment
                    probe = add(anchor, mul(direction, max(value * .005, .0001)))
                    if body.pointContainment(p3(probe)) != outside:
                        # A concave fillet has material on the outward side.
                        # Keep the radial annotation in its opening instead.
                        radius = math.sqrt(dot(sub(anchor, center), sub(anchor, center)))
                        end = add(anchor, mul(direction, -travel))
                        if travel > radius * .9:
                            tolerance = max(min(travel * .001, .0001), 1e-6)
                            start_free = add(anchor, mul(direction, -max(tolerance * 4, travel * .001)))
                            if not segment_is_clear(design.rootComponent, visible_solids(design.rootComponent), start_free, end, tolerance):
                                raise ValueError('Radial leader intersects a solid; adjust the offset')
                    if body.pointContainment(p3(end)) != outside:
                        raise ValueError('No free radial label position; adjust the offset')
                segments.append((anchor, end))
                label = end
                prefix = 'R ' if kind == 'radius' else '⌀'
        coords = [n for segment in segments for pt in segment for n in pt]
        lines = group.addLines(adsk.fusion.CustomGraphicsCoordinates.create(coords), [], False)
        if not lines: raise RuntimeError('Failed to create graphics lines')
        color = adsk.fusion.CustomGraphicsSolidColorEffect.create(adsk.core.Color.create(0, 0, 0, 255))
        lines.color = color
        lines.weight = 1
        units = design.unitsManager
        unit_name = 'deg' if kind == 'angle' else units.defaultLengthUnits + '^2' if kind == 'area' else units.defaultLengthUnits
        caption = ((ident + ': ') if ident else '') + prefix + units.formatValue(value, unit_name, True)
        # The line plane remains model-based; text orientation can flip for readability.
        # Keep the label's nominal height independent of the measured value and
        # the zoom level. The view scale affects text only, not its model plane.
        size = 1.0
        matrix = adsk.core.Matrix3D.create()
        if not matrix.setWithCoordinateSystem(p3(label), adsk.core.Vector3D.create(*text_x), adsk.core.Vector3D.create(*text_y), adsk.core.Vector3D.create(*text_z)):
            raise RuntimeError('Failed to orient dimension text')
        text = group.addText(caption, 'Arial', size, matrix)
        if not text: raise RuntimeError('Failed to create graphics text')
        # The scaling anchor is expressed in the text's local coordinates,
        # before its transform, rather than in model coordinates.
        scale = adsk.fusion.CustomGraphicsViewScale.create(16, p3((text.width / 2, -size * .25, 0)))
        if not scale: raise RuntimeError('Failed to create text view scale')
        text.viewScale = scale
        text.color = color
        text.depthPriority = 10
        text.isSelectable = False
        _LABELS[id(group)] = (text, label, text_x, text_y, size, None, face_camera)
        if kind == 'angle' and hasattr(adsk.core, 'Application'):
            _ANGLES[id(group)] = (lines, apex, x, y, value, offset)
        orient_text(group, camera)
        return group
    except Exception:
        forget(group)
        group.deleteMe()
        raise
