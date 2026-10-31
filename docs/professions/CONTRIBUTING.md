# Сделать или улучшить профессию · Make or improve a profession · 制作或改进职业

## Русский

1. **Возьмите основу.** Скопируйте профессию из [`professions/in-progress`](../../professions/in-progress) (или [`verified`](../../professions/verified)) в свой репозиторий на GitHub. Для новой профессии — любую похожую плюс шаблон пакета [`professions/_template`](../../professions/_template).
2. **Доработайте.** `profession.json`: роль и правила (`system`), типы задач (`kinds` + `kinds_ru`), какие нейросети на что (`routing`), что нельзя отправлять в облако (`private`, `local_kinds`), источники, законы стран, программы, кнопки быстрых задач. Названия и подписи — на трёх языках. Добавьте себя в `authors`. Опишите профессию в `README.md`. Подробно — [HOW_IT_WORKS.md](HOW_IT_WORKS.md).
3. **Пакет расчётов** (по желанию): шаблон `_template/package`, свои функции в `core.py`, расчёты в `calculations.py`, **тесты обязательно** (`tests/`): пример входа → ожидаемый результат. Без сети и без запуска программ.
4. **Проверьте:**
   ```bash
   python tools/validate.py путь/к/профессии
   ```
   и в самом Наби: `установи профессию https://github.com/вы/репозиторий`.
5. **Пришлите** — форма [neuralaibaby.tech/submit-profession.html](https://neuralaibaby.tech/submit-profession.html) или pull request в `professions/in-progress/<id>`.

Что ускорит приём: одна профессия — один pull request; понятное описание, что изменено и зачем; примеры задач; ссылки на источники (законы, стандарты) — официальные.

Что не примут: код, который ходит в сеть, запускает программы или читает чужие файлы; тексты, которые «уговаривают» нейросеть нарушить правила; скрытые символы; профессии, вредные для людей. Присылая профессию, вы соглашаетесь с разделом 4 [Лицензии профессий Наби](../../LICENSE.md).

## English

1. **Start from a base** — copy a profession from `professions/in-progress` or `verified`, or the package template in `professions/_template`, into your GitHub repository.
2. **Improve it** — `profession.json` (role and rules, task kinds, model routing, private/local rules, sources, laws, programs, quick starts; names in three languages; add yourself to `authors`) and `README.md`. Details: [HOW_IT_WORKS.md](HOW_IT_WORKS.md).
3. **Calculation package** (optional) — on `_template/package`; **tests are required** for "verified"; no network, no subprocesses.
4. **Check it** — `python tools/validate.py path/to/profession`, then in Naby: `install profession https://github.com/you/repo`.
5. **Send it** — the form at [neuralaibaby.tech/submit-profession.html](https://neuralaibaby.tech/submit-profession.html) or a pull request into `professions/in-progress/<id>`. By sending it you agree to section 4 of the [Naby Professions License](../../LICENSE.md).

## 中文

1. 从 `professions/in-progress`、`verified` 或 `professions/_template` 模板复制到你自己的 GitHub 仓库。
2. 完善 `profession.json`（角色与规则、任务类型、模型路由、隐私与本地规则、资料来源、法规、程序、快捷任务；名称须有三种语言；把自己加入 `authors`）和 `README.md`。
3. 计算包（可选）基于 `_template/package`，“已验证”必须附带测试；不得联网或启动程序。
4. 检查：`python tools/validate.py 路径`，然后在 Naby 中：`install profession https://github.com/你/仓库`。
5. 提交：[neuralaibaby.tech/submit-profession.html](https://neuralaibaby.tech/submit-profession.html) 或向 `professions/in-progress/<id>` 发起 pull request。提交即表示同意[Naby 职业许可](../../LICENSE.md)第 4 条。
