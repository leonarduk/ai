# Documentation

This directory contains setup guides, reference materials, and architectural documentation for the AI Systems Lab project.

---

## Setup Guides

### [Ollama Setup Guide](ollama_setup_guide.md)
Complete guide to setting up Ollama for running local LLMs. Covers:
- Installation on Windows/Mac/Linux
- Downloading and managing models
- Basic usage and API access
- Integration with development tools

---

## Reference Materials

Additional reference PDFs and documentation are stored locally in:
```
/PRIVATE/reference-materials/
```

This directory is gitignored to keep the repository lean. Reference materials include:
- Model comparison charts
- Research papers
- External documentation
- Vendor guides

---

## Architecture Documentation

### Planned Content

The following architecture documentation is planned for future development:

#### System Architecture
- Overall system design and component interactions
- Data flow diagrams
- Integration patterns

#### MCP Server Architecture
- Server interaction flows
- Protocol specifications
- Client-server communication patterns
- Security and authentication models

#### Deployment Architecture
- Cloud infrastructure design (AWS)
- Container orchestration (Kubernetes)
- CI/CD pipeline architecture
- Monitoring and observability setup

---

## Contributing to Documentation

When adding new documentation:

1. **Setup guides** → Add to this directory with descriptive filename
2. **Project-specific docs** → Add to relevant project's `/docs` folder
3. **Architecture decisions** → Create ADR (Architecture Decision Record) in project folder
4. **Reference materials** → Store in `/PRIVATE/reference-materials/` (not committed)

---

## Documentation Standards

### File Naming
- Use lowercase with hyphens: `setup-guide-name.md`
- Be descriptive: `aws-deployment-guide.md` not `deployment.md`

### Content Structure
- Start with overview/purpose
- Include prerequisites
- Provide step-by-step instructions
- Add troubleshooting section
- Link to related documentation

### Code Examples
- Use syntax highlighting
- Include comments
- Show expected output
- Provide working examples

---

*Part of the [AI Systems Lab](../README.md) portfolio*
