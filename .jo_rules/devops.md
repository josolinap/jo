# DevOps Rules

- **CI First**: Before pushing, run relevant tests if available.
- **Zero-Downtime**: When modifying service-layer code (`supervisor/`), ensure backward compatibility.
- **Logging**: Ensure all new features have appropriate logging using Jo's `log` pattern.
- **Atomic Commits**: Group related changes into single, descriptive commits.
