"""Screen-space caption packing, independent of Fusion and model geometry."""
import math


def projection_scale(width, height, target):
    """Normalize projection pixels to viewport points on high-DPI displays.

    The camera look-at target projects to the viewport centre. Fusion can report
    that projection in backing pixels while width/height use logical points.
    Snap only coherent positive ratios; ordinary/fake viewports default to 1.
    """
    if not width or not height or target is None:
        return 1.0
    sx, sy = 2*target[0]/width, 2*target[1]/height
    if not all(math.isfinite(v) and .5 <= v <= 4 for v in (sx, sy)):
        return 1.0
    scale = (sx+sy)/2
    if abs(sx-sy) > .05:
        return 1.0
    snapped = round(scale*4)/4
    return snapped if abs(snapped-scale) <= .03 else scale


def projected_caption_size(width, height, xdirection, ydirection):
    """Conservative AABB of an oriented text rectangle in screen pixels."""
    def direction(value, fallback):
        length = math.hypot(*value)
        return tuple(v/length for v in value) if length > 1e-8 else fallback
    # At grazing angles a projected axis can collapse. Reserve a conservative
    # full-size perpendicular extent instead of accepting a zero-height box.
    known_y = direction(ydirection, (0, 1))
    x = direction(xdirection, (-known_y[1], known_y[0]))
    y = direction(ydirection, (-x[1], x[0]))
    return abs(x[0])*width+abs(y[0])*height, abs(x[1])*width+abs(y[1])*height


def choose_caption(width, height, occupied, candidates, padding=5, bounds=None):
    """Select the first actual projected candidate with clear padded bounds.

    Candidates yield ((screen_x, screen_y), payload). The adapter supplies
    projected positions reachable in the caption's model plane.
    """
    if not all(math.isfinite(v) and v > 0 for v in (width, height)):
        raise ValueError('Invalid caption size')
    for (x, y), payload in candidates:
        if not math.isfinite(x) or not math.isfinite(y):
            continue
        rect = (x-width/2-padding, y-height/2-padding,
                x+width/2+padding, y+height/2+padding)
        if bounds is not None and not (bounds[0] <= rect[0] and bounds[1] <= rect[1]
                                       and rect[2] <= bounds[2] and rect[3] <= bounds[3]):
            continue
        if all(rect[2] <= other[0] or other[2] <= rect[0] or
               rect[3] <= other[1] or other[3] <= rect[1] for other in occupied):
            return payload, rect
    raise ValueError('Cannot find a clear caption position in this view')
