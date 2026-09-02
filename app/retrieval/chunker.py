from pathlib import Path


def chunk_markdown(file_path: Path) -> list[dict[str, str]]:
    """Split a Markdown document into chunks based on ## headings."""

    text = file_path.read_text(encoding="utf-8")

    chunks = []
    current_header = None
    current_lines = []

    for line in text.splitlines():

        # Start a new chunk when we find a level-2 heading
        if line.startswith("## "):

            # Save the previous chunk before starting a new one
            if current_header is not None:
                content = "\n".join(current_lines).strip()

                chunks.append(
                    {
                        "source": f"{file_path.name}::{current_header}",
                        "content": content
                    }
                )

            current_header = line[3:].strip()
            current_lines = [line]

        # Add lines only after we've entered a ## section
        elif current_header is not None:
            current_lines.append(line)

    # Save the final chunk
    if current_header is not None:
        content = "\n".join(current_lines).strip()

        chunks.append(
            {
                "source": f"{file_path.name}::{current_header}",
                "content": content
            }
        )

    return chunks