from django import template

register = template.Library()


@register.filter
def can_edit(user, document):
    """{% if user|can_edit:document %} -> object-level check (owner or Reviewer)."""
    return user.has_perm("documents.change_document", document)
