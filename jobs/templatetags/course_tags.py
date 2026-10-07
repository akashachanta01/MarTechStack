from django import template

register = template.Library()


@register.filter
def inr(value):
    """60000 -> '₹60,000', 100000 -> '₹1,00,000' (Indian digit grouping)."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return value
    s = str(n)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + tail
    return "₹" + s


@register.filter
def usd(value):
    try:
        return "US${:,}".format(int(value))
    except (TypeError, ValueError):
        return value
