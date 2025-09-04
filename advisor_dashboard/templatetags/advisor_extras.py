from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary using a key"""
    return dictionary.get(key)

@register.filter
def get_attr(obj, attr):
    """Get an attribute from an object"""
    return getattr(obj, attr, None)
