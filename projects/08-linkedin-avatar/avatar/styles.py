"""Copy and CSS for the Gradio chat UI. Structure adapted from
ed-donner/agents `1_foundations/twin/styles.py`; palette and copy are our own.
"""

TITLE = "Steve Leonard — AI Twin"

DESCRIPTION = (
    "This is Steve's AI twin. Ask about his background or any project in his "
    "GitHub — it reads both. It'll tell you when it doesn't know."
)

EXAMPLE_QUESTIONS = [
    "What's his experience with Python and financial services?",
    "Tell me about issue-worm.",
    "Would he be a good fit for a staff engineering role?",
    "How do I get in touch with him?",
]

FOOTER_MARKDOWN = (
    "An email given to this chat is sent to Steve as a one-off notification — "
    "not stored, not added to a list, not shared."
)

CSS = """
:root {
    --avatar-accent: #2f6fed;
    --avatar-accent-dark: #7fa8ff;
    --avatar-muted: #5b6270;
    --avatar-muted-dark: #9aa2b1;
}

.gradio-container {
    max-width: 760px !important;
    margin: 0 auto !important;
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
}

#avatar-header {
    text-align: center;
    padding: 0.5rem 0 1rem 0;
}

#avatar-header h1 {
    font-size: 1.5rem;
    margin-bottom: 0.25rem;
    color: var(--avatar-accent);
}

.dark #avatar-header h1 {
    color: var(--avatar-accent-dark);
}

#avatar-header p {
    color: var(--avatar-muted);
    font-size: 0.95rem;
    margin: 0;
}

.dark #avatar-header p {
    color: var(--avatar-muted-dark);
}

#avatar-footer {
    text-align: center;
    font-size: 0.8rem;
    color: var(--avatar-muted);
    padding-top: 0.75rem;
    margin-top: 0.5rem;
    border-top: 1px solid rgba(0, 0, 0, 0.08);
}

.dark #avatar-footer {
    color: var(--avatar-muted-dark);
    border-top-color: rgba(255, 255, 255, 0.08);
}

@media (max-width: 480px) {
    .gradio-container {
        padding: 0.5rem !important;
    }
    #avatar-header h1 {
        font-size: 1.2rem;
    }
    #avatar-header p {
        font-size: 0.85rem;
    }
}
"""
