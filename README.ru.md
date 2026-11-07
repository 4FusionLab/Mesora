# 4FusionLab · Шаблон аддина Autodesk Fusion

[English](README.md)

Готовая основа для новых аддинов **Autodesk Fusion / Fusion 360** от 4FusionLab: рабочая команда, манифест, тестируемая Python-логика, CI на трёх ОС, сборка ZIP, GitVersion и автоматические GitHub Releases.

## Как создать аддин

1. Нажми **Use this template → Create a new repository** в организации `4FusionLab`.
2. В новом репозитории запусти **Actions → Initialize add-in → Run workflow**. Имя репозитория станет именем Python-пакета; название в Fusion и описание можно задать отдельно.
3. Инициализатор создаст **уникальные UUID манифеста и ID команды**, переименует папку аддина, подготовит README на английском и русском. Повторная генерация ID запрещена.
4. Добавляй реализацию в Python-пакет. Запускай `python -m unittest discover -s tests -v` и `python scripts/build.py --version 0.1.0`.
5. После инициализации push/merge в `main` публикует релиз **только при изменении поставляемого кода или ресурсов**, после успешного CI. Документация и тесты сами по себе релиз не запускают.

При необходимости инициализируй локально: `python scripts/init_addin.py --name MyNewAddin --display-name "My New Add-in"`. Затем закоммить изменения и отправь в свой репозиторий.

**Не устанавливай исходную папку `FusionAddin` как готовый продукт:** шаблон намеренно помечен неинициализированным.

## Что унифицировано

- GitVersion.Tool **6.8.2**, Conventional Commits, неизменяемые версии и автоматические теги без ручной работы.
- Общие GitHub Actions из [4FusionLab/.github](https://github.com/4FusionLab/.github), подключённые по точному SHA.
- Offline-тесты на Linux, macOS и Windows и отдельная проверка в самом Fusion.
- Проверка ZIP, манифеста, SHA-256 и release notes.
- Раздельные английская/русская документации и базовый `AGENTS.md` для AI-агентов.

Инструкция по разработке и приёмке — в [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

