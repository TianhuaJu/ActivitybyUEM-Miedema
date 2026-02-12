# CLAUDE.md - AlloyThermolCal Pro

## Project Overview

AlloyThermolCal Pro is a desktop thermodynamic calculation application for alloy systems based on the UEM-Miedema model framework. It provides activity calculations, phase diagrams, precipitation temperature prediction, and an AI-assisted chat interface for natural language interaction.

## Quick Reference

### Run

```bash
python Main.py
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

Required: `numpy`, `scipy`, `matplotlib`, `PyQt5`

### Build (PyInstaller)

```bash
pyinstaller AlloyActApp_Optimized.spec
```

### Test

```bash
python test_phase_stability.py
```

No pytest/unittest framework is configured. Tests are minimal.

## Project Structure

```
├── Main.py                    # Entry point (PyQt5 splash screen + main window)
├── calculations/              # Core thermodynamic calculation engines
├── core/                      # Element class, constants, database handler, TDB parser
├── models/                    # Miedema model, extrapolation models, interaction parameters
├── gui/                       # PyQt5 widget classes (one widget per tab)
├── llm/                       # LLM integration: backends, chat agent, tools, memory
├── database/data/             # SQLite databases (DataBase.db, compounds.db, unary50.tdb)
├── utils/                     # Data logger
├── docs/                      # Feature documentation
├── calculation_logs/          # Auto-generated calculation logs (gitignored content OK)
└── resources/                 # Icons and assets
```

### Key Module Relationships

- `llm/tools.py` wraps `calculations/` and `models/` as LLM-callable tool functions
- `llm/chat_agent.py` orchestrates LLM backends with tool execution loops
- `gui/ChatWidget.py` renders chat messages (Markdown + LaTeX -> HTML)
- `gui/Alloyact_GUI_Pro.py` is the main window with tabbed interface
- `core/element.py` loads element data from `database/data/DataBase.db`

## Code Style Guidelines

### Language

- **Code identifiers**: English (snake_case functions, PascalCase classes)
- **Comments and docstrings**: Chinese (Mandarin)
- **Git commit messages**: English, imperative present tense
- **Error messages to users**: Chinese

### Naming Conventions

- Functions and variables: `snake_case`
- Classes: `PascalCase` (e.g., `ThermodynamicProperties`, `ChatAgent`)
- Constants: `UPPER_CASE` (e.g., `SYSTEM_PROMPT`, `TOOL_SCHEMAS`)
- Private members: `_leading_underscore` (e.g., `_thermo_calc`, `_get_client`)
- Qt signals: `snake_case` with descriptive names (e.g., `response_ready`, `tool_called`)

### Docstrings

Use Chinese docstrings. Short one-liner or multi-line with `参数:` and `返回:` sections:

```python
def calculate_liquidus_temperature(self, composition: Dict[str, float]) -> Dict[str, Any]:
    """计算液相线温度"""

def calculate_precipitation_temperature(self, alloy_composition, solute_element, ...):
    """
    计算合金中指定溶质的析出温度。

    参数:
        alloy_composition: 合金组成 {元素: 摩尔分数}
        solute_element: 溶质元素符号

    返回:
        Dict: 包含析出温度等信息的字典
    """
```

### Type Annotations

Use type annotations on function signatures. Not required on every local variable:

```python
def chat(self, user_message: str) -> str:
def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
```

### Imports

Order: stdlib -> third-party -> local. Use `sys.path.insert` for cross-module imports:

```python
import json
from typing import Dict, List, Any
from dataclasses import dataclass

from PyQt5.QtWidgets import QWidget, QVBoxLayout

from llm.tools import ThermodynamicTools
```

### Indentation

4 spaces (not tabs). Some legacy files use tabs — do not introduce new tabs.

### Line Length

No strict limit enforced. Keep lines readable; ~120 characters is the practical maximum.

## LLM Tool System

### Adding a New Tool

1. Add schema to `TOOL_SCHEMAS` dict in `llm/tools.py`
2. Add description to `TOOL_DESCRIPTIONS` dict
3. Implement the method on `ThermodynamicTools` class
4. Register in `_get_all_tool_methods()` return dict
5. Add LLM type coercion in `_coerce_arguments()` if needed
6. Add keyword mapping in system prompt (`llm/chat_agent.py` SYSTEM_PROMPT)
7. Add fallback formatter in `_format_single_result()` or `_format_batch_results()`
8. Add Chinese tool name to `_TOOL_NAMES_ZH` dict

### Tool Return Convention

All tools return `Dict[str, Any]` with `"status": "success"` or `"status": "error"` + `"message"`.

### Chat Message Rendering Pipeline (gui/ChatWidget.py)

1. LaTeX math conversion (block `$$...$$` and inline `$...$`)
2. Greek letters and symbol replacement
3. Subscript/superscript processing
4. **Markdown table -> HTML table** (before `\n` -> `<br>`)
5. Markdown formatting (headers, bold, code, lists)
6. Newline -> `<br>`

## Common Pitfalls

- LLMs sometimes pass numeric values as strings — `_coerce_arguments()` handles this
- `composition` values must be mole fractions summing to 1.0 — `_normalize_composition()` handles this
- `calculation_logs/` files are auto-appended during calculations; expect them to change when running tests
- The `database/data/DataBase.db` is read-only at runtime; never write to it
- Qt `QLabel` only supports a subset of HTML/CSS — no `<thead>`, limited CSS properties
