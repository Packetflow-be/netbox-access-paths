"""
The questionnaire export: every way into a customer, one row per path, as CSV or Markdown. Shaped for NIS2 and
supplier security questionnaires ("how exactly do you access our systems?").
"""
import csv
import io

from django.utils import timezone
from django.utils.translation import gettext as _

from . import __version__
from .utils import plugin_setting

FORMATS = ('csv', 'markdown')


def _columns(include_credential_ref):
    columns = [
        ('customer', _('Customer')),
        ('path', _('Access path')),
        ('target', _('Target')),
        ('method', _('Method')),
        ('origin', _('Starts from')),
        ('through', _('Through')),
        ('who', _('Who')),
        ('authentication', _('Authentication')),
    ]
    if include_credential_ref:
        columns.append(('credential_ref', _('Credential kept in')))
    columns += [
        ('status', _('Status')),
        ('approved_by', _('Approved by')),
        ('approved_on', _('Approved on')),
        ('reviewed_on', _('Last reviewed')),
        ('review_by', _('Review by')),
        ('expires', _('Expires')),
    ]
    return columns


def include_credential_ref():
    return bool(plugin_setting('export_credential_ref'))


def _hop_text(hop):
    return hop.label or str(hop.hop)


def build_rows(paths):
    rows = []
    for path in paths:
        target = path.target_display or ''
        if path.is_scope:
            target = _('everything in {type} {name}').format(type=path.target_type.name, name=target)
        if path.target_type_id and path.target_url:
            target = f'{target} ({path.target_url})'
        who = [c.name for c in path.holders.all()] + [_('group {name}').format(name=g.name)
                                                      for g in path.holder_groups.all()]
        rows.append({
            'customer': path.tenant.name,
            'path': str(path),
            'target': target or _('(target missing)'),
            'method': path.get_method_display(),
            'origin': path.route.get_origin_display(),
            'through': ' -> '.join(_hop_text(h) for h in path.all_hops),
            'who': ', '.join(who),
            'authentication': path.get_authentication_display(),
            'credential_ref': path.credential_ref,
            'status': path.get_status_display(),
            'approved_by': path.approved_by.name if path.approved_by else '',
            'approved_on': path.approved_on.isoformat() if path.approved_on else '',
            'reviewed_on': path.reviewed_on.isoformat() if path.reviewed_on else '',
            'review_by': path.review_by.isoformat() if path.review_by else '',
            'expires': path.expires.isoformat() if path.expires else '',
        })
    return rows


def to_csv(rows, credential_ref=False):
    columns = _columns(credential_ref)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([label for _key, label in columns])
    for row in rows:
        writer.writerow([row[key] for key, _label in columns])
    return out.getvalue()


def _md_cell(value):
    return str(value).replace('\\', '\\\\').replace('|', '\\|').replace('\r', ' ').replace('\n', ' ') or ' '


def to_markdown(rows, title, credential_ref=False):
    columns = _columns(credential_ref)
    lines = [
        f'# {title}',
        '',
        _('Generated {date} by netbox-access-paths {version}. {count} access paths.').format(
            date=timezone.localdate().isoformat(), version=__version__, count=len(rows)),
        '',
        '| ' + ' | '.join(label for _key, label in columns) + ' |',
        '|' + '---|' * len(columns),
    ]
    for row in rows:
        lines.append('| ' + ' | '.join(_md_cell(row[key]) for key, _label in columns) + ' |')
    return '\n'.join(lines) + '\n'
