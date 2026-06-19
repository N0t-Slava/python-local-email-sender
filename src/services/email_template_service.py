from dataclasses import dataclass

from jinja2 import Environment, StrictUndefined, select_autoescape
from jinja2.exceptions import TemplateError


class EmailTemplateRenderError(ValueError):
    pass


@dataclass(frozen=True)
class RenderedEmailContent:
    subject: str
    body: str
    html_body: str | None


def _build_template_environment(autoescape: bool):
    return Environment(
        autoescape=select_autoescape(
            enabled_extensions=("html", "xml"),
            default_for_string=autoescape,
            default=autoescape,
        ),
        undefined=StrictUndefined,
    )


def render_template_string(
        template: str | None,
        context: dict,
        autoescape: bool = False,
) -> str:
    if template is None:
        return ""
    
    try:
        env = _build_template_environment(autoescape=autoescape)
        return env.from_string(template).render(context)
    except TemplateError as exc:
        raise EmailTemplateRenderError(str(exc)) from exc
    

def render_email_template(
    subject_template: str,
    body_template: str,
    html_body_template: str | None,
    context: dict,
) -> RenderedEmailContent:
    return RenderedEmailContent(
        subject=render_template_string(
            subject_template,
            context,
            autoescape=False,
        ),
        body=render_template_string(
            body_template,
            context,
            autoescape=False,
        ),
        html_body=render_template_string(
            html_body_template,
            context,
            autoescape=True,
        )
        if html_body_template is not None
        else None,
    )
