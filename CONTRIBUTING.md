# Contributing to ArrakisEngine

Thank you for your interest in contributing to ArrakisEngine! This document provides guidelines for contributing to the project.

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/ArrakisEngine.git
   cd ArrakisEngine
   ```
3. **Set up** the development environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # macOS/Linux
   pip install -r requirements-dev.txt
   cd frontend && pnpm install && cd ..
   ```
4. **Copy** the example config:
   ```bash
   cp config.yaml.example config.yaml
   # Edit config.yaml with your Stockfish path and player details
   ```
5. **Create a branch** for your feature or fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Workflow

### Running Tests

```bash
# Run all unit tests
pytest tests/ -v

# Run specific test file
pytest tests/test_models.py -v

# Skip tests requiring Stockfish or live APIs
pytest tests/ -v -k "not stockfish and not integration and not live"
```

### Running the App

```bash
# Start the backend server
python main.py dashboard

# In another terminal, start the frontend
cd frontend && pnpm dev
```

### Code Style

- Python: Follow PEP 8 conventions
- TypeScript/React: Follow existing patterns in the codebase
- Use meaningful variable names and add docstrings to functions
- Keep functions focused and reasonably sized

## Submitting Changes

1. **Commit** your changes with clear, descriptive messages
2. **Push** to your fork
3. **Open a Pull Request** against the `main` branch
4. **Describe** what your PR does and why

### PR Guidelines

- Keep PRs focused on a single feature or fix
- Include tests for new functionality
- Ensure all existing tests pass
- Update documentation if needed

## Contributor License Agreement (CLA)

By submitting a pull request, you agree to the following:

- You grant the project maintainer (Bernard Leong) a perpetual, worldwide, non-exclusive, royalty-free, irrevocable license to use, modify, and distribute your contributions under any license.
- This is necessary because ArrakisEngine uses a dual-licensing model (AGPL-3.0 open source + commercial license). The CLA ensures the maintainer can continue to offer both options.
- You confirm that you have the right to submit the contribution and that it does not violate any third-party rights.

## Reporting Issues

- Use GitHub Issues for bug reports and feature requests
- Include steps to reproduce for bugs
- Include your OS, Python version, and Stockfish version

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). Please read it before participating.

## Questions?

Open a GitHub Discussion or Issue if you have questions about contributing.
