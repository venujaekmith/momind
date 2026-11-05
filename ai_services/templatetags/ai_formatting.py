import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe


register = template.Library()


def _inline_format(value):
    """Apply a small, escaped subset of Markdown used by AI summaries."""
    value = escape(str(value).strip())
    value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"`(.+?)`", r"<code>\1</code>", value)
    value = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", value)
    return value


def _is_table_divider(line):
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _table_row(line, cell_tag):
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return "<tr>" + "".join(
        f"<{cell_tag}>{_inline_format(cell)}</{cell_tag}>" for cell in cells
    ) + "</tr>"


@register.filter(name="format_ai_summary")
def format_ai_summary(value):
    """Render AI Markdown as readable, escaped report HTML.

    This intentionally supports only the structures requested in the risk
    prompt. All model-provided text is escaped before markup is introduced.
    """
    if not value:
        return ""

    lines = str(value).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    output = []
    paragraph = []
    open_list = None
    index = 0

    def close_paragraph():
        if paragraph:
            output.append(f"<p>{' '.join(paragraph)}</p>")
            paragraph.clear()

    def close_list():
        nonlocal open_list
        if open_list:
            output.append(f"</{open_list}>")
            open_list = None

    while index < len(lines):
        raw_line = lines[index].strip()

        if not raw_line:
            close_paragraph()
            close_list()
            index += 1
            continue

        if re.fullmatch(r"-{3,}", raw_line):
            close_paragraph()
            close_list()
            index += 1
            continue

        # Markdown table: header row, separator row, then zero or more rows.
        if (
            raw_line.startswith("|")
            and index + 1 < len(lines)
            and _is_table_divider(lines[index + 1])
        ):
            close_paragraph()
            close_list()
            output.append('<div class="ai-report-table-wrap"><table class="ai-report-table"><thead>')
            output.append(_table_row(raw_line, "th"))
            output.append("</thead><tbody>")
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                output.append(_table_row(lines[index], "td"))
                index += 1
            output.append("</tbody></table></div>")
            continue

        heading = re.match(r"^(#{1,4})\s+(.+)$", raw_line)
        bold_heading = re.fullmatch(r"\*\*(.+?)\*\*\s*", raw_line)
        if heading or bold_heading:
            close_paragraph()
            close_list()
            heading_text = heading.group(2) if heading else bold_heading.group(1)
            output.append(f"<h3>{_inline_format(heading_text)}</h3>")
            index += 1
            continue

        numbered = re.match(r"^\d+[.)]\s+(.+)$", raw_line)
        bullet = re.match(r"^[-*]\s+(.+)$", raw_line)
        if numbered or bullet:
            close_paragraph()
            required_list = "ol" if numbered else "ul"
            if open_list != required_list:
                close_list()
                output.append(f"<{required_list}>")
                open_list = required_list
            output.append(f"<li>{_inline_format((numbered or bullet).group(1))}</li>")
            index += 1
            continue

        close_list()
        paragraph.append(_inline_format(raw_line.rstrip()))
        index += 1

    close_paragraph()
    close_list()
    return mark_safe("".join(output))
