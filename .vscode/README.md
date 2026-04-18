# 🎯 VSCode Configuration Directory

This folder contains all VSCode-specific configurations for the CV + Job Tracker project.

## 📁 Contents

### `settings.json`
Main VSCode settings file with configurations for:
- **Python Development**: Black formatter, Ruff linter, Pylance type checking
- **JavaScript/TypeScript**: Prettier formatter, ESLint
- **Editor Behavior**: Tab size, line length, formatting on save
- **File Associations**: Custom associations for `.typ` (Typst), `.env` files
- **Search & Explorer**: Exclusion patterns for better performance

**Key Settings:**
- Python interpreter: `.venv/bin/python`
- Line length rulers: 80, 100, 120 characters
- Auto-format on save: enabled
- Tab size: 2 for JS/TS, 4 for Python

### `extensions.json`
Lists all recommended VSCode extensions organized by category:
- **Python**: ms-python.python, Pylance, Black, Ruff
- **JavaScript/TypeScript**: ESLint, Prettier, Tailwind CSS
- **DevOps**: Docker, Remote Containers, Remote SSH
- **Productivity**: GitLens, GitHub Copilot, Todo Tree
- **Documentation**: YAML, TOML, Makefile support

When you open this project in VSCode, you'll be prompted to install these extensions.

### `launch.json`
Debug configurations for:
- **Python Main Script**: Run `main.py` with full debugging
- **FastAPI**: Start the API server with reload
- **Pytest**: Run tests with verbose output
- **Node.js Web Dev**: Launch Vite dev server
- **Chrome Debugger**: Debug web app in browser

**Compound Configuration:**
- "Full Stack: Python + Web" - Runs FastAPI + Vite simultaneously

### `tasks.json`
Build and run tasks for quick execution:
- **Python Tasks**: Install deps, run main script, run tests, format code, lint
- **FastAPI Tasks**: Start development server
- **Node.js Tasks**: Install deps, dev server, build
- **Docker Tasks**: Full stack up/down
- **Code Quality**: Ruff linting, Black formatting, Prettier formatting

Run tasks via: `Cmd+Shift+P` → "Tasks: Run Task"

## 🚀 Quick Start

### 1. Open Project in VSCode
```bash
code .
```

### 2. Install Extensions
VSCode will show a notification to install recommended extensions. Click **"Install All"**.

Or manually install key extensions:
```bash
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension esbenp.prettier-vscode
code --install-extension dbaeumer.vscode-eslint
```

### 3. Select Python Interpreter
1. Open Command Palette: `Cmd+Shift+P`
2. Search: "Python: Select Interpreter"
3. Choose: `./.venv/bin/python`

### 4. Verify Setup
Run the verification:
```bash
bash setup-ide.sh
```

Or manually verify:
```bash
python3 --version      # Should be 3.9+
node --version         # Should be 18+
npm --version          # Should be 9+
```

## ⚙️ Key Features

### Auto-Formatting
- **On Save**: All files automatically format when saved
- **Manual**: `Cmd+Shift+I` to format current file
- **Python**: Black (100 char line length)
- **Web**: Prettier (80 char line length)

### Linting
- **Python**: Ruff (fast, comprehensive)
- **JavaScript/TypeScript**: ESLint
- Issues appear in the Problems panel

### Debugging
Press `F5` to start debugging with the default configuration (Python Main).

Change debug target via Debug dropdown (top-left debug icon).

### Running Tasks
Open Command Palette (`Cmd+Shift+P`) and type:
- `Tasks: Run Task` → Select from list
- `Python: Run Tests`
- `Build Web App`

### Git Integration
- **GitLens**: View blame annotations (hover over lines)
- **Git Graph**: Visual branch history

## 🐍 Python Workflow

### Format Code
```bash
# Cmd+Shift+I in VSCode or:
black .
```

### Lint Code
```bash
ruff check .
```

### Run Tests
```bash
# F5 with pytest config, or:
pytest tests/ -v
```

### Check Types
```bash
mypy .
```

## 📝 JavaScript/TypeScript Workflow

### Format Code
```bash
# Cmd+Shift+I in VSCode or:
cd apps/web && npm run format
```

### Lint Code
```bash
cd apps/web && npm run lint
```

### Build
```bash
cd apps/web && npm run build
```

## 🔍 Finding Things

| Task | Shortcut |
|------|----------|
| Open file | `Cmd+P` |
| Find in files | `Cmd+Shift+F` |
| Go to definition | `Cmd+Click` or `F12` |
| Find references | `Shift+F12` |
| Rename symbol | `F2` |
| Format document | `Cmd+Shift+I` |
| Open terminal | `Ctrl+`` |

## 🐛 Troubleshooting

### Python not found
- Go to: `Cmd+Shift+P` → "Python: Select Interpreter"
- Choose `./.venv/bin/python`

### Extensions not installing
- Check internet connection
- Try: `code --install-extension <extension-id>`
- Restart VSCode

### Formatter conflicts
- Make sure only one formatter is set per language
- In settings.json, check `"editor.defaultFormatter"`

### Port already in use (Vite 5173)
```bash
# Find and kill process
lsof -i :5173
kill -9 <PID>

# Or use different port
npm run dev -- --port 3000
```

### IntelliSense not working
1. Reload VSCode: `Cmd+Shift+P` → "Developer: Reload Window"
2. Check Python interpreter is selected
3. Make sure `.venv` is activated

## 📚 Resources

- [VSCode Python Guide](https://code.visualstudio.com/docs/languages/python)
- [VSCode Debugging](https://code.visualstudio.com/docs/editor/debugging)
- [VSCode Tasks](https://code.visualstudio.com/docs/editor/tasks)
- [Black Documentation](https://black.readthedocs.io/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Prettier Documentation](https://prettier.io/docs/)

## 📖 More Information

For a comprehensive setup guide, see: `SETUP_GUIDE.md`

---

**Last Updated**: 2025
**Tested on**: VSCode 1.95+, macOS 13+, Python 3.9-3.12, Node 18+