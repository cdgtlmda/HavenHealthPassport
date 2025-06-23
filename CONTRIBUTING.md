# Contributing to Haven Health Passport

Thank you for your interest in contributing to Haven Health Passport. This guide explains how to contribute to the project.

## Code of Conduct

Haven Health Passport serves displaced refugees and vulnerable populations. All contributions must prioritize:
- Patient safety and data security
- Medical accuracy
- Accessibility for users with limited technology access
- Respect for diverse backgrounds

## Getting Started

1. Fork the repository
2. Clone your fork
3. Set up the development environment (see [Development Setup](docs/06-development/development-environment.md))
4. Create a feature branch
5. Make your changes
6. Submit a pull request

## Development Process

### Branch Naming
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring

### Commit Messages
Follow conventional commit format:
```
feat: add patient verification API
fix: resolve offline sync issue
docs: update API documentation
```

### Code Standards

#### TypeScript/JavaScript
- TypeScript with strict mode enabled
- No `any` types
- 100% type coverage
- ESLint and Prettier configured

#### Python
- Python 3.11+
- Type hints required
- Black formatting
- Pylint compliance

### Testing Requirements
- Write tests for all new features
- Maintain >90% test coverage
- All tests must pass before PR submission
- Use real AWS services for testing (no mocks)

## Pull Request Process

1. Update documentation for any API changes
2. Add tests for new functionality
3. Ensure all tests pass
4. Update the README.md if needed
5. Request review from maintainers

### PR Checklist
- [ ] Tests pass
- [ ] Documentation updated
- [ ] Code follows style guidelines
- [ ] Security implications reviewed
- [ ] Accessibility verified
- [ ] Healthcare compliance checked

## Healthcare Compliance

All contributions must maintain:
- HIPAA compliance
- FHIR R4 standards
- HL7 compatibility
- Medical terminology accuracy

## Security

- Never commit credentials or secrets
- Follow security best practices
- Report security issues privately to security@havenhealthpassport.org

## Questions?

- Open an issue for general questions
- Check existing documentation in `/docs`
- Contact maintainers for guidance

## License

By contributing to this project, you agree that your contributions will be licensed under the Apache License, Version 2.0, the same license as the project.

### Important Notes on Apache 2.0:
- Your contributions automatically grant copyright and patent licenses to all users
- You retain copyright of your contributions
- You grant a perpetual, worldwide, non-exclusive, royalty-free patent license
- If you submit on behalf of your employer, ensure you have permission to do so

See the [LICENSE](LICENSE) file for full details.