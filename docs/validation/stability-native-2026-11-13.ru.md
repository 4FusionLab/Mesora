# Mesora: нативная проверка стабильности, 13.11.2026

**Текущий итог: [Mesora 1.1.0 опубликована](https://github.com/4FusionLab/Mesora/releases/tag/v1.1.0), macOS-приёмка и публикационные gates пройдены.** Проверены 144 offline tests, native macOS scope, CI Linux/macOS/Windows, реальная установка ZIP и скачанные release assets. Тег v1.1.0 указывает на `ecdc98556a20bb9d71f5630cc70a1b156e97c217`; ZIP/манифест/checksum согласованы. Текущее experimental-обозначение снято по выполненному условию пользователя. Windows Fusion нативно не проверялась; границы evidence сохраняются. Ниже — история прежних ревизий и результаты, а не открытые дефекты текущего релиза.

## Начальный прогон: среда и границы доказательства (история)

macOS, Autodesk Fusion `2706.1.17`. Проверял основной агент, единственный владелец общей Fusion-сессии. База checkout: `a28bedb`, с текущими изменениями кандидата. Все изменения геометрии и сохранения выполнялись только на двух новых синтетических цилиндрах в тестовой области `_Preferences`. Открытую пользовательскую модель не редактировали, не сохраняли и не закрывали. Полный restart Fusion не выполняли из-за открытого изменённого пользовательского документа.

Вызовы Fusion API проходили через MCP script. Запуск команды через `CommandDefinition.execute()` не оставлял открытый Mesora-диалог; прямые UI-действия не дали подтверждённого изменения интерфейса. Поэтому данные ниже **не являются** приёмкой реального OK/Cancel или порядка UI save/commandTerminated events. Прямой вызов `notify` отмечен отдельно; он проверяет обработчик на настоящей CAD-геометрии, но не доставку события.

## Исторический S19 через прежний способ запуска — FAIL

Фикстура `Mesora stable acceptance 2026-11-13`:

1. Создан цилиндр радиусом 2 cm и высотой 4 cm. Через рабочий `Execute('add')` записаны две строки: скрытый `m1` Radius и видимый `m2` Edge Length; одна graphics group. В attributes — schema v2, references, offsets и индивидуальная видимость.
2. `Document.saveAs(...)` вернул `True`. После возврата и повторной проверки: `isModified=False`, одна tracked group, `removed_for_save=False`. Предсохранительная очистка при этом пути не выполнилась. Точную причину отсутствия очистки/доставки события в MCP-контексте считать открытой; не переносить этот результат на непроверенный UI Save.
3. Mesora остановлена, документ закрыт без дополнительных изменений, сохранённая версия открыта снова. Mesora controls отсутствуют, одно BRep body, `customGraphicsGroups.count=0`, документ чистый. **Визуально размер m2 всё ещё виден.**
4. Без Mesora радиус изменён с 2 до 2.5 cm. Сохранение вернуло `True`, close/reopen успешны, радиус остаётся 2.5 cm, одно body, API graphics count по-прежнему 0, документ чистый.
5. Визуально по-прежнему видна старая подпись `m2 L=125.7 mm`, хотя актуальная окружность имеет длину около 157.1 mm. Модель геометрически доступна для работы без аддина, но полная совместимость **не принята** из-за ложной аннотации.

Снимки только синтетического viewport сохранены локально, не включены в пакет:

- `dist/local-validation/orphan-without-mesora.png` — после reopen с остановленным Mesora;
- `dist/local-validation/orphan-after-model-edit.png` — устаревшая подпись после изменения радиуса и save/reopen.

Оба снимка просмотрены. CAD-архивы не изменялись для обхода дефекта; пользовательские файлы и версии не удалялись.

SHA-256 `orphan-after-model-edit.png`: `47c07c3a99df266aa8c1e12a354f6dccb5c8963172855bb3e61238e891f02c27`.

## Контрольный путь с явной очисткой — частичный PASS

Фикстура `Mesora safe UI acceptance 2026-11-13`:

1. Сначала сохранён чистый цилиндр без графики. Затем через рабочий `Execute('add')` применены два измерения: `m1` hidden, offset 0.2 cm; `m2` visible, offset 0.3 cm. В памяти и storage две строки, одна graphics group.
2. Радиус sketch circle изменён с 1.5 до 2 cm. **Прямо вызван** `UpdateDimensions.notify`. Fingerprint изменился, graphics group перестроилась, измеренная длина актуальной edge составила `12.566370614359172 cm`. Это подтверждает работу обработчика с настоящей геометрией; автоматический event-trigger остаётся PENDING.
3. **Прямо вызван** `DocumentEvent('saving').notify` перед API save. После обработчика groups=0, removed_for_save=True. Save=True, документ чистый.
4. Mesora остановлена, close/reopen без Mesora: groups=0, body=1, документ чистый. Снимок `dist/local-validation/prepared-save-without-mesora.png` просмотрен — остаточных размеров нет.
5. Mesora снова запущена. `current_state` загрузил две строки, hidden_ids=`m1`, offsets=`0.2/0.3`, next_id=3. Ссылка m2 разрешена, актуальная длина `12.566370614359172 cm`; явный Refresh без ошибок создал одну группу.
6. Тестовый документ закрыт; пользовательский документ оставлен открытым. Mesora запущена. Run on Startup ранее был включён, настройку в этом прогоне не меняли.

Этот путь доказывает сохранение определений и полезность очистки. Он **не закрывает** требования нормального Save/Save As/restart без ручной подготовки и не заменяет S19 FAIL.

SHA-256 контрольного `prepared-save-without-mesora.png`: `098843b277603d26619d798adfa1661b5a66e4e8ed763b6585408446b3d226fe`.

## Локальные quality gates первоначального этапа

На кандидате первоначального этапа (`271d25e`) прошли компиляция, **103 offline tests**, `scripts/check_project.py`, `git diff --check` и CI Linux/macOS/Windows. Проверена детерминированная сборка 54 файлов с новыми модулями и четырьмя иконками; UUID сохранён. Локальный ZIP `dist/stability-validation/Mesora-0.0.0.zip` имеет SHA-256 `fcf1dce909048810f39033c400e67d46351eee138d083e3099a30afe49214381`. `0.0.0` — только числовая заглушка для проверки упаковки, не назначенная версия релиза. Штатную версию определяет GitVersion 6.8.2. Этот ZIP не публиковать как stable.

## Продолжение: проверка способа запуска и автоматическое восстановление

Пользователь уточнил контракт: **без Mesora размеры не показываются вообще**. В документе сохраняются только определения; отображение создаёт запущенная Mesora. Геометрия должна оставаться доступна без аддина.

При продолжении CUA явно сообщил, что Mac заблокирован и автоматическая разблокировка не удалась. Запрошена ручная разблокировка. Это ограничивает предыдущие попытки UI: они не подтверждают ни открытие команды, ни штатные события сохранения. До повторного прогона точная причина отсутствия предсохранительной очистки остаётся открытой; нельзя приписывать её только Autodesk или только Mesora.

Выполнен штатный перезапуск через `Application.scripts.itemByPath(...).stop()` и, отдельным вызовом, `Script.run(False)`, без ручного `exec` entrypoint. Подтверждены `isRunning=True`, `isRunOnStartup=True`, один загруженный entrypoint и 14 обработчиков до новых изменений. Независимый custom-event probe пока не подтвердил доставку callback. Такой probe не является проверкой Save и не закрывает событийну́ю приёмку.

Добавлен отдельный development observer `scripts/native_acceptance_observer.py`. Он регистрирует реальные document/command events и собственный custom event, пишет JSONL с порядком, активной командой/средой, состоянием tracked graphics и SHA-256 definitions. Он не вызывает продуктовые обработчики и не меняет CAD. Пользовательские документы исключены из инспекции, tokens/payload не записываются. Наблюдатель не входит в ZIP.

В коде кандидата добавлена загрузка definitions по владельцу документа при `documentOpened` и запуске аддина. Отрисовка запрашивается отложенно и блокируется Drawing/native-командой. Активация документа возвращает только уже существующий запрос восстановления; Save сбрасывает его, чтобы queued startup/open не перезапустил source-save loop. Ошибка schema одного документа не блокирует загрузку остальных. Автономно прошли **113 тестов**, включая 10 новых регрессий; нативная доставка и отображение этого этапа пока PENDING до разблокировки Mac.

## Необходимая повторная проверка

Продолжить проверку через штатный Script Manager, с независимо подтверждённой доставкой событий. Отдельно повторить API Save/Save As, чтобы отличить ограничение прежней ручной перезагрузки Python от продуктовой ошибки. Штатный GUI Save и отсутствие размеров без аддина в последнем прогоне проходят; это не закрывает все save/recovery пути. `isModified` не подделывать, вымышленные transient-флаги не вводить. Принять model edits, Undo/Redo, Drawing, несколько документов, restart и установку финального ZIP отдельно на macOS и Windows.

## Актуальный прогон после разблокировки: штатный lifecycle

Источник: `f090654`, Fusion 2706.1.17. Основной агент выполнил GUI-действия; продуктовые `notify` напрямую не вызывались.

### S09 / S10 / S19: сохранение и работа без аддина

- Штатные `Script.stop()` и `Script.run(False)` выполнены отдельными вызовами. При открытии `Mesora safe UI acceptance 2026-11-13 v2` Mesora автоматически загрузила две записи, скрытый m1, offsets 0.2/0.3 cm, и создала одну группу m2.
- Настоящие Cmd+S и OK в Save дали ровно v3: документ чистый, groups=0, removed_for_save=True, restore_requested=False. Постсохранительного пересоздания не было.
- После остановки аддина и close/reopen v3: isRunning=False, body=1, groups=0, документ чистый. Снимок `dist/local-validation/unlocked-ui-save-no-addon.png` просмотрен: размеров нет. SHA-256 `098843b277603d26619d798adfa1661b5a66e4e8ed763b6585408446b3d226fe`.
- С остановленным аддином radius изменён с 2 до 2.3 cm. Настоящий GUI Save дал v4; close/reopen без аддина сохранил radius=2.3, body=1, groups=0, чистый документ. Снимок `dist/local-validation/unlocked-no-addon-edited.png` просмотрен: размеров нет. SHA-256 `fac1e56fbaae1a61825fbf55faba0783219a10eeeed282daa5cf3b826e58cdf4`.
- Запуск Mesora восстановил две записи, одну группу, hidden_ids=m1, прежние offsets. Ссылка разрешилась по новой геометрии: длина `14.451326206513047 cm`, на экране `144.5 mm`.

Таким образом, **S19 macOS PASS для проверенного GUI-пути**, включая изменение и сохранение без аддина и последующее восстановление. Это не полный Fusion restart и не Windows-проверка.

### S12 / S13: Save As и отмена

Отмена GUI Save As сохранила две записи, одну группу и hidden_ids=m1. Настоящий Save As создал `Mesora Save As acceptance 2026-11-13 v1`: документ чистый, groups=0, removed_for_save=True, две сохранённые записи. Независимость дальнейших изменений копии и reopen копии без аддина требуют завершения.

Для создания копии исчерпан лимит editable документов: **только ранее созданная нами** фикстура `Mesora stable acceptance 2026-11-13` переведена в Read-Only штатным UI. Пользовательские документы не переводились в другой режим и не удалялись.

### Независимое подтверждение событий

Observer, импортированный напрямую через MCP, не получал callback и непригоден как доказательство. Генератор `scripts/prepare_native_observer.py` создаёт отдельный development add-in в `dist/native-acceptance/MesoraAcceptanceObserver`; он запущен штатным менеджером, startup=False. В его `events.jsonl` подтверждены:

```text
4  customEvent.callback
14 commandStarting PLM360SaveAsCommand         groups=1
20 commandStarting PLM360SaveCommand           groups=1
22 documentSaving                              groups=0 removed_for_save=True
23 documentSaved                               groups=0 removed_for_save=True
24 commandTerminated PLM360SaveCommand          groups=0
```

Definitions SHA-256 в сохранении не изменился. Это реальная доставка событий и очистка перед сохранением; отсутствие callback в прежнем MCP-observer не доказывало отсутствия продуктового события.

### S04 / S05 / S07: применение глазиков и Undo/Redo

На копии настоящий Mesora-диалог показал m1 Radius=23.0 mm hidden/offset=2 mm и m2 Edge Length=144.5 mm visible/offset=3 mm. Общий глазик выключил preview (0 групп), повторное включение сохранило скрытие m1. Глазик m2 скрывал строку без удаления: обе строки остались. OK записал hidden_ids=m1,m2 в память и attributes, groups=0. GUI Undo восстановил hidden_ids=m1, GUI Redo снова дал hidden_ids=m1,m2. Состояние editor_open=False после применения. **Это PASS метаданных, но не графики Undo:** первоначальная оценка только по `len(state.groups)` была недостаточной и отозвана.

Последующее чтение того же managed trace обнаружило D06:

```text
29–31 после Commit:                tracked=0  actual groups=0
34–37 во время/после Undo:         tracked=0  actual groups=1
38–39 перед Redo (после refresh):  tracked=1  actual groups=2
40–43 во время/после Redo:         tracked=1  actual groups=0
46–49 следующий Undo:             tracked=0  actual groups=1
```

Fusion самостоятельно восстановила удалённую графику Undo-транзакцией. Прежний refresh создавал ещё одну группу, поскольку не знал о восстановленном API-объекте. **S07 graphics FAIL, D06 Major**, блокирует stable. Прежний PASS на основании tracked-state не переносится.

Исправление кандидата: каждая новая группа получает `CustomGraphicsGroup.id` со стабильным UUID-префиксом Mesora и уникальным suffix. `renderer.owned_groups/erase_owned` перечисляют реальные root groups и удаляют только помеченные Mesora-группы, включая восстановленные wrappers; чужие и старые группы без метки не присваиваются. `State.erase(keep=staged)` сохраняет новые staged-группы до commit и проверяет реальную коллекцию при refresh/save/stop, даже если tracked-state пуст. Ошибка удаления сохраняет ссылки и отменяет Save. Writable string `id` подтверждён [официальной документацией](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_CustomGraphicsGroup_id.htm).

После интеграции **119 offline tests PASS**, включая воспроизведение нового wrapper с сохранённым ownership ID, пустого tracked-state, чужих groups, staged groups и retry после отказа удаления. Нативно ещё требуется подтвердить, что Fusion сохраняет `id` при настоящем Undo, и повторить Undo/Redo→Save→stop→reopen с визуальным снимком. Это исправление не объявлено нативно принятым.

Позднее этот несохранённый этап копии закрыт через Don't Save; исходная сохранённая копия v1 не переписана этими настройками. Это проверка транзакций текущей сессии, не сохранённой изоляции двух файлов.

### Незавершённое параметрическое изменение и внешний сбой

На повторно открытой синтетической копии добавлен radial constraint d3=23 mm. Открыт нативный Change Parameters, раскрыт Sketch1. Изменение значения не завершено: после клавиатурного перехода и чтения AX-дерева CUA вернул noWindowsAvailable/timeoutReached, MCP перестал отвечать. Снятый без завершения процесса sample показывает основной поток в цепочке AX hierarchy → QMacAccessibilityElement.accessibilitySelectedChildren → обработчик сигнала libcer → read. Python/Mesora-фреймов на этом стеке нет; причинность за пределами этих наблюдений не установлена.

Нативный S06 **INCONCLUSIVE**, не PASS. Процесс не завершался принудительно, поскольку открыт несохранённый пользовательский документ. Запрошена ручная проверка Fusion. См. [наблюдатель и восстановление](observer-and-ax-recovery-2026-11-13.ru.md). До восстановления отзывчивости невозможно штатно остановить managed observer; его логи находятся только в ignored dist и не входят в продуктовый ZIP.

Предыдущий Drawing/visibility прогон находится в [отдельном отчёте](drawing-visibility-2026-11-13.ru.md). Его PASS не переносится автоматически на текущие persistence/update изменения. Полная [матрица CJM](stable-release-cjm-2026-11-13.ru.md) сохраняет PENDING и FAIL.

## API-основания

- [DocumentEventArgs](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_DocumentEventArgs.htm): установленный API имеет `isOperationCancelled` и `cancelReason`; `isSaveCanceled` отсутствует. Исправлен используемый символ. Реальная отмена сохранения при fault-injection ещё не принята.
- [Custom event queue](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Application_fireCustomEvent.htm): работа выполняется в основном потоке при idle; перед refresh дополнительно исключается активная native-команда.
- [CustomGraphics persistence report](https://forums.autodesk.com/t5/fusion-support-forum/bug-report-custom-graphics-serialized-into-a-document-are/td-p/14142906): внешнее описание похожего дефекта; решение о блокировке основано на нашем воспроизведении выше.

Релиз не опубликован; сообщение пользователю Telegram о готовом релизе не отправляется до успешного выпуска.

## Итог повторной приёмки fe68881

### Ownership и Undo/Redo

В Fusion подтверждено сохранение ownership `CustomGraphicsGroup.id` при настоящем Undo. Дополнительная регрессия неизменных definitions/fingerprint потребовала сверять реальные owned IDs с валидными tracked wrappers; исправление вошло в `fe68881`. No-op OK → UI Undo/Redo сохраняет tracked=valid=actual=owned=1. Скрытие второй строки даёт 0/0; Undo возвращает 1/1, Redo — 0/0, повторный Undo — 1/1. GUI Save копии v1→v2, managed stop, close/reopen без аддина: clean, actual=0, визуально нет размеров (`ownership-undo-save-no-addon.png`). **D06 RETEST PASS в этом macOS scope.**

### Параметрическое изменение

После сбоя Parameters Fusion показала Crash Reporter. Он закрыт без отправки отчёта; процесс завершился самостоятельно. После запуска recovery list закрыт без открытия или удаления файлов. Это не доказательство восстановления пользовательского документа. Qt Accessibility stack не устанавливает причину сбоя Mesora.

Вместо повторного чтения проблемной AX-таблицы использован отдельный managed development command `FourFusionLabAcceptanceRadius`: меняет только d3 в указанной синтетической копии, в собственной Fusion-транзакции; не вызывает Mesora handlers. Радиус 23→27 mm автоматически изменил label 144.5→169.6 mm без Refresh. Фактическая длина 16.964600329384883 cm, fingerprint актуален, tracked=valid=actual=owned=1. GUI Edit → Undo Multiple → Undo Acceptance Radius вернул 144.5 mm; GUI Redo без промежуточных MCP-вызовов вернул 169.6 mm. Оба состояния проверены визуально. Это native SDK-command acceptance; ручное редактирование в Parameters остаётся INCONCLUSIVE.

### Drawing

`NewFusionDrawingDocumentCommand` запущена при видимой графике. В managed observer session `622f1b9a-2259-4479-a9d5-9dc7fb1b7e2b`: saving108 видит group1, saved109 — group0, clean. Source копия v2→v3 ровно один раз. Открыт `FusionDocumentationEnvironment` с настоящим листом и Drawing View. Размещение base view отменено, несохранённый тестовый Drawing закрыт через Don't Save. Возврат в source: v3, isModified=False, tracked=actual=0, radius2.7 cm. Сценарий создания листа и source-save loop принят; размещение/оформление видов не заявляется.

### Штатный полный restart и работа без Mesora

Оба development add-ins остановлены. Единственная открытая модель — синтетическая чистая копия v3. Выполнен Cmd+Q; отсутствие процесса Fusion подтверждено до нового запуска. Обычный launch прошёл через Preparing your experience в Home, без Crash Reporter. Открытие копии v3 при автоматически запущенной Mesora: isRunning=True, isRunOnStartup=True, 2 definitions, hidden m1, tracked=actual=1, radius2.7 cm; визуально label169.6 mm.

Затем Mesora остановлена, копия закрыта через Don't Save (отбрасывается только отрисованная сессионная графика), v3 открыта вновь: isModified=False, actual=0, radius2.7 cm, Mesora isRunning=False. Визуально размеров нет. Исходный файл v4 и копия v3 затем открыты одновременно без аддина: исходник radius2.3 cm, копия radius2.7 cm, оба clean и actual0. Подтверждена независимость геометрии Save As; отдельный цикл редактирования definitions в копии не заявляется. В конце штатный запуск Mesora восстановлен; Run on Startup сохранён.

### Проверки и оставшиеся gates

Повторно **122 offline tests PASS**, project validator PASS. CI для runtime `fe68881`: [run12 success](https://github.com/4FusionLab/Mesora/actions/runs/43462948414), Linux/macOS/Windows — код и ZIP, не Fusion.

Финальная локальная проверочная сборка: `Mesora-0.0.0.zip`, SHA-256 `157c00aa5726d097d837c17b635cdfaf81e316241158bc63bfbc7130ed4f19c0`. Числовая заглушка 0.0.0 не является версией для публикации. Development observer/driver не входят в ZIP.

Пользователь подтвердил отсутствие доступной Windows с Fusion и уточнил publication scope: успешные обязательные gates macOS достаточны для выпуска и снятия experimental. Windows остаётся отдельно UNVERIFIED и сама по себе не блокирует выпуск. PR остаётся draft, main не изменяется, релиз и Telegram-анонс не выполнены.

## Уточнения пользователя и текущий открытый дефект

После указания не сохранять тестовые файлы все дальнейшие сохранения CAD/экспорты тестовых моделей остановлены. Запрос перевода тестового файла в Read-Only отменён. По явному запросу пользователя root закрыл без сохранения два открытых saved fixtures и удалил четыре ранее созданных синтетических облачных файла: Mesora safe UI acceptance 2026-11-13, Mesora stable acceptance 2026-11-13, Mesora Save As acceptance 2026-11-13 и Mesora visibility acceptance. `DataFile.deleteMe()` вернул True для каждого; повторный поиск Mesora в `_Preferences` вернул 0. Пользовательские модели не затронуты. Открыт один несохранённый synthetic all-types fixture для визуального исправления.

На нём управляемый независимый SDK harness подтвердил все семь численных типов и roundtrip settings в attributes, real deleted reference retention и отказ перезаписывать corrupt/future schema. Настоящая Mesora GUI показала восемь строк (семь типов плюс недоступная ссылка), Enter сохранил восемь definitions в несохранённой модели. Изменение типа edge_length→radius показало 27.0 mm; Escape отменил эту правку и изменение глазика. GUI очистка недоступной геометрии и удаление только этой строки оставили все семь остальных типов. Это не приёмка создания каждого типа мышью и не файловый roundtrip.

Обнаружено неограниченное удержание command handlers. Исправление `6a0663e` освобождает command scopes при destroy. **128 offline tests PASS**. Нативно: Add open appHANDLERS16/scopes1/bindings5, Escape appHANDLERS16/scopes0/editorFalse; второй Add с изменением глазика и OK оставил appHANDLERS16/scopes0 и valid=tracked=actual=6. Прежний pipeline PASS относится к fe68881, не этому новому commit.

**D07 Major OPEN:** при одновременном отображении шести размеров на текущей геометрии подписи перекрываются и плохо читаются. Это реальный провал визуальной приёмки, независимо от численного PASS. Снимок до исправления: `dist/local-validation/caption-overlap-before.png`. Исправление совместного размещения подписей и повторная визуальная проверка в работе. Experimental пока не снимается.

## Исправление наложений и окончательное решение для orbit

Первая версия совместного размещения устранила статические наложения, но пользователь подтвердил скачки при вращении. Предпочтение предыдущей позиции на `8129f2f` дало нулевое смещение на отдельных 2°/14° samples, однако обычное пользовательское вращение всё ещё прыгало. Эти samples не закрывали дефект.

В `a77502e` CameraChanged **только ориентирует текст**: размещение подписей не пересчитывается вообще, геометрия угловой дуги заморожена после рендера. Раскладка выполняется при явном добавлении/изменении набора, Refresh и восстановлении набора. Удалён промежуточный перенос текста к base и обратно. В почти реберном ракурсе первоначальное размещение использует устойчивую видимую ось; Retina-проекция нормализуется.

После managed reload проверено фактически загруженное code object: cameraRepack=False, angleRebuild=False. Настоящие изменения Camera на 45°, 90° и возврат 0° дали на каждом шаге WORLD anchorDeltas=[0,0,0,0,0,0], неизменный массив координат дуги, tracked=actual=6. Пользователь повторил обычное вращение и сообщил: **«Теперь не скачут»**. D07 закрыт для воспроизведённого macOS набора; это не гарантия отсутствия любых проекционных перекрытий на произвольном реберном ракурсе.

**144 offline tests PASS**, compilation/validator/diff check PASS. [CI run15 success](https://github.com/4FusionLab/Mesora/actions/runs/43475119273) относится к `a77502e`, не переносится с прежнего commit.

## Установка ZIP и заключительный несохранённый полигон

Проверочный ZIP из `a77502e`: 56 файлов, stable UUID сохранён, `label_layout.py` и `event_scope.py` внутри, helper-аддины отсутствуют. Placeholder version 0.0.0 не для публикации. SHA-256 `eb0395fd9b876def94d91599e8bd20105010e80398342b14135c80da29e6bc65`.

ZIP распакован и реально подключён через managed Scripts API. Подтверждены модуль из распакованной папки, 16 app handlers, command scopes0, 5 definitions, 7 measurement definitions, tracked=valid=actual=6, orbit reflow отсутствует, angle rebuild отсутствует. После испытаний пакет остановлен и отвязан; штатная рабочая папка Mesora снова подключена, isRunning=True, Run on Startup=True.

В отдельном временном **несохранённом** документе повторно прошёл seven-type SDK suite. Затем выполнен native assembly-context suite: parent и child имеют по Rz90 и ненулевые translations. Три мировые точки совпали с независимым расчётом: (8,21,30), (5,21,35), (2,17,35). Семь измерений root/top/nested и circle radius/diameter/length совпали с аналитикой; явное форматирование дало 27.0 mm и 1.0 in. После перемещения parent по X на 1 cm расстояние root→nested стало sqrt(1702)=41.255302689472536 cm. Это приёмка reference resolution/measure после движения, не отдельный end-to-end auto-update аннотации сборки. Исходные definitions context suite не менял; его графика очищена.

Проверка реального выбора: public selection setters сами не доставили picker inputChanged, поэтому их success не использован как доказательство пользовательского выбора. Пользователь кликнул грани; независимый managed observer получил **четыре настоящих picker inputChanged**: area с одной BRepFace → distance с двумя → area → distance. Esc отменил draft, editor=False/scopes0, исходные 8 definitions временного документа сохранены. Никаких искусственных событий или ручных вызовов product handlers.

Временный документ закрыт через close(False), оба helpers остановлены/отвязаны. Возврат в исходный несохранённый документ: ровно 7 типов m1…m7, hidden m4, прежние offsets 0…0.3 cm, global=True, tracked=actual=6, handlers16/scopes0. Изоляция A→B→A подтверждена. Никаких новых облачных сохранений или CAD-экспортов не выполнялось.

По прямому поручению пользователя организовано последовательное владение общей Fusion-сессией с Planara через общий журнал FUSION_SESSION.md; передача только после явного подтверждения, не по таймауту. Оставшаяся проверка UI-переходов типов подготовлена локально, до возврата слота Fusion не вызывается.

## Заключительный пакет UI-типов и native Measure

После явного возврата слота Planara root сверил SelectCommand, creationId `2835aa87-f636-4741-a54f-a6476e579ba2`, один исходный несохранённый документ и startup=True. Managed TypeProbe выполнил 13 переключений публичных dropdown inputs: получены 13 **настоящих kind inputChanged**, совпали draft kind, выбранный пункт и значения по аналитике. Все исходные типы восстановлены, definitions неизменны. Это нативные UI-события, не заявление о физическом нажатии мышью на каждый тип.

Для цилиндрической боковой грани r=27 mm/h=30 mm проверено: edges2, loops2, coEdges1+1; сумма длин edges, coEdges и результат адаптера одинаковы — 33.929200658769766 cm. Нативная команда **MeasureCommand** с той же выбранной гранью показала **Loop Length 339.292 mm**, Area5089.38 mm², Radius27 mm и Diameter54 mm. Root просмотрел настоящий Measure palette screenshot. Таким образом, предварительная неоднозначность учёта шва для этой фикстуры снята — seam edge в её loops нет.

Measure закрыт, selection очищен; TypeProbe остановлен/отвязан. Финальный checkpoint: SelectCommand, одна исходная несохранённая модель, editor=False/scopes0, 7 definitions/6 groups, Run on Startup=True. После этого слот явно предложен Planara и принят её координатором; никакие Fusion вызовы со стороны Mesora до нового согласования не выполняются. QA-helper RuEnProbe существовал отдельно и не изменялся.

## Preflight стабильного пакета 1.1.0

GitVersion 6.8.2 в PR CI определил MajorMinorPatch=1.1.0. После снятия текущего experimental-обозначения прошли 144 tests, validator, compileall и diff check; RU README alias совпадает. Две независимые сборки `Mesora-1.1.0.zip` побайтно одинаковы, SHA-256 `4790d87dbfad91834c9ba3863943a9e23974130cd58c3f87dc38418ed9938c2b`. Сравнение с нативно установленным проверочным ZIP подтвердило одинаковые 56 файлов и идентичный runtime: отличаются только первая строка docstring Mesora.py и description/version манифеста. Stable UUID и прочие поля манифеста сохранены. Финальная публикация и проверка скачанных assets выполняются штатным pipeline, без ручных tags.

## Публикация и проверка скачанных артефактов

PR #3 объединён проверенным squash commit `ecdc98556a20bb9d71f5630cc70a1b156e97c217`. [Main workflow run17](https://github.com/4FusionLab/Mesora/actions/runs/43481689168) успешно выполнил metadata/version/release-eligibility, все три offline/package jobs и publishing job. GitVersion 6.8.2 выпустил **1.1.0**; тег создан только штатным pipeline и указывает на этот commit. Release опубликован как final, не draft/prerelease.

Root скачал из опубликованного Release `Mesora-1.1.0.zip` и `.zip.sha256`. ZIP проходит testzip, содержит 56 файлов с единственной корневой папкой Mesora; embedded manifest version1.1.0, stableUUID89072f8c-cdca-48bf-8a2a-440c9ae898e6, description без experimental. SHA-256: `4790d87dbfad91834c9ba3863943a9e23974130cd58c3f87dc38418ed9938c2b`. Он совпадает с опубликованным checksum, GitHub asset digest и локальной воспроизводимой preflight-сборкой; ZIP совпадает побайтно.

После публикации исправлены только две относительные ссылки в тексте release notes: русская версия и матрица evidence получили абсолютные URL. Разрешённое редактирование notes сохранило тот же release ID, tag target, published_at, asset IDs/sizes/digests; tag/ZIP/checksum не заменялись. Соответствующая документация и итоговый протокол обновлены отдельным docs-only commit. Новых CAD-save или Fusion вызовов для этого не выполнялось.
