# Accountant_AI — AI ESF Pre-Check Copilot (Kazakhstan MVP)

Этот README описывает, как **2 разработчика** могут параллельно собрать MVP за ~6 часов без хаоса.

## 1) Цель MVP
Собрать демо-сервис, который:
- принимает CSV/XLSX с инвойсами;
- проверяет данные до отправки в ИС ЭСФ;
- показывает статусы `OK / Warning / Critical`;
- выдает список ошибок и рекомендаций;
- формирует AI/rule-based summary;
- экспортирует проверенный результат в CSV.

## 2) Роли команды (2 разработчика)

### Developer A — Data & Validation Lead (Backend Logic)
**Зона ответственности:** ядро проверки и риск-скоринг.

**Делает:**
1. `validator.py`
   - чтение DataFrame;
   - 10 правил валидации;
   - список issues по строкам;
   - `risk_score`, `status`, `recommended_action`.
2. Нормализацию входных колонок.
3. Обработку ошибок формата (пустой файл, нет нужных колонок).
4. Подготовку результата в единый DataFrame для UI/экспорта.

**Definition of Done (DoD):**
- минимум 7–10 правил работают стабильно;
- каждая строка имеет `status`, `issues`, `risk_score`;
- корректно работает на good/bad sample.

---

### Developer B — UI & Demo Lead (Streamlit + UX)
**Зона ответственности:** интерфейс, сценарий демо и экспорт.

**Делает:**
1. `app.py`
   - upload CSV/XLSX;
   - кнопка `Check invoices`;
   - KPI карточки (`total`, `critical`, `warning`, `ok`);
   - таблица результатов;
   - фильтр `show only problematic`;
   - сортировка critical first.
2. `summarizer.py`
   - summary блок (LLM или rule-based шаблоны).
3. Экспорт в CSV (`checked_results.csv`).
4. Визуальный polish: цвета статусов, короткий disclaimer.

**Definition of Done (DoD):**
- пользователь проходит сценарий upload → check → results → export;
- summary виден и читаем;
- UI понятен без объяснений.

## 3) Общий контракт между A и B
Чтобы работать параллельно, фиксируем единый формат данных после проверки.

### Входные поля (минимум)
- `invoice_id`
- `invoice_date`
- `seller_bin`
- `buyer_bin`
- `amount_without_vat`
- `vat_amount`
- `total_amount`
- `currency`
- `contract_number` **или** `description`

### Выходные поля (обязательные)
- `invoice_id`
- `status` (`OK`, `Warning`, `Critical`)
- `risk_score` (0–100)
- `issues` (строка с `;`-разделителем или list)
- `issues_count`
- `recommended_action`

> Важно: Developer B не меняет структуру, которую отдает Developer A.

## 4) Таймлайн на 6 часов (для 2 человек)

### Час 1
- A: каркас `validator.py`, интерфейс функции `validate_invoices(df)`.
- B: базовый `app.py` с upload и заглушкой результатов.

### Час 2
- A: реализует базовые правила (пустые поля, BIN, суммы, даты).
- B: подключает вызов `validate_invoices`, выводит таблицу.

### Час 3
- A: риск-скоринг + классификация статусов.
- B: KPI карточки + фильтр проблемных + сортировка.

### Час 4
- A: стабилизация edge cases, дубликаты invoice_id.
- B: `summarizer.py` и блок “Top 3 issues”.

### Час 5
- A: тестирует на sample_good / sample_bad, багфикс.
- B: экспорт CSV, UI polish, disclaimer.

### Час 6
- Вместе: прогон demo-сценария 60–90 секунд, финальные правки.

## 5) Минимальные правила валидации (MVP)
Почему именно **10 правил**:
- это не фиксированное требование и не «магическое число»;
- это практичный baseline для 6-часового MVP: покрывает обязательные поля, базовую математику, даты и дубликаты;
- при таком объёме уже видно ценность (документы реально делятся на OK/Warning/Critical), но команда не тонет в edge-case логике в первую ночь.

Если времени меньше — можно сократить до 6 правил. Если времени больше — расширить до 15–20 (например, проверки по валютам, ставкам НДС, бизнес-правилам по контрагентам).

1. Пустой `invoice_id`.
2. Пустой `invoice_date`.
3. Пустой `seller_bin` / `buyer_bin`.
4. BIN невалидного формата.
5. `amount_without_vat <= 0`.
6. `vat_amount < 0`.
7. Несходится математика: `amount_without_vat + vat_amount != total_amount` (с допуском).
8. Дубликат `invoice_id`.
9. Дата в будущем / слишком старая.
10. Пустой `description` (или `contract_number`).

## 6) Структура проекта
```
.
├── app.py
├── validator.py
├── summarizer.py
├── sample_good.csv
├── sample_bad.csv
├── requirements.txt
└── README.md
```

## 7) Git workflow для 2 разработчиков

### Вариант (рекомендуется)
- `dev-a-validation` — ветка Developer A
- `dev-b-ui` — ветка Developer B

Порядок:
1. B стартует UI c мок-данными.
2. A завершает контракт `validate_invoices(df)`.
3. B подтягивает ветку A и подключает реальную логику.
4. Совместный merge в `main` (или demo-branch).

### Commit convention
- `feat(validation): add invoice rules and risk scoring`
- `feat(ui): add upload, status cards and export`
- `feat(summary): add rule-based AI summary`
- `chore(samples): add good and bad demo csv`

## 8) Критерий “готово к показу утром”
MVP готов, если:
- загружается файл;
- работают 7–10 правил;
- есть `OK/Warning/Critical`;
- есть summary;
- есть export CSV;
- demo проходит без фраз “тут пока не работает”.

## 9) Quick start (после реализации файлов)
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 10) Demo script (60–90 сек)
1. “Вот выгрузка из бухгалтерской системы.”
2. “Загружаем файл в AI ESF Pre-Check Copilot.”
3. “Сервис находит критичные ошибки до отправки.”
4. “Вот приоритетные документы и рекомендации.”
5. “Экспортируем результат для исправления.”
6. “Следующий шаг — интеграция с 1С/ИС ЭСФ.”

## 11) Что уже решает текущий MVP (сейчас)
Это не только AI summary. Текущий MVP уже закрывает практический pre-check цикл:
- принимает CSV/XLSX и показывает preview;
- валидирует документы (через `validator.py`, а при его отсутствии — demo fallback в `app.py`);
- присваивает `OK / Warning / Critical`;
- считает `risk_score` и формирует `recommended_action`;
- показывает Top-issues и batch summary;
- экспортирует checked CSV для бухгалтера.

AI summary — это верхний слой объяснения результатов, а не единственная функция продукта.

## 12) Groq LLM summary (optional)
Если нужен реальный LLM summary вместо rule-based:

```bash
export GROQ_API_KEY="<your_groq_api_key>"
# optional
export GROQ_MODEL="llama-3.1-8b-instant"
streamlit run app.py
```

Поведение:
- если `GROQ_API_KEY` задан, `summarizer.py` запрашивает summary через Groq API;
- если ключ не задан или API недоступен — автоматически используется rule-based fallback;
- в UI под блоком **AI Summary** показывается источник: `Groq LLM` или `Rule-based template`.

> В целях безопасности ключ не хранится в репозитории и не хардкодится в коде.

