from django.utils.translation import gettext_lazy as _

from utilities.choices import Choice, ChoiceSet

# Each choice set has a `key`, so an installation can replace or extend it with NetBox's FIELD_CHOICES setting,
# e.g. FIELD_CHOICES = {'netbox_access_paths.AccessPath.method+': [('winrm', 'WinRM', 'blue')]}.


class OriginChoices(ChoiceSet):
    """Where sessions on a route start."""
    key = 'AccessRoute.origin'

    OFFICE = 'office'
    ZTNA = 'ztna'
    HOME = 'home'
    CUSTOMER_SITE = 'customer_site'
    INTERNET = 'internet'

    CHOICES = [
        Choice(OFFICE, _('Office network'), color='blue'),
        Choice(ZTNA, _('ZTNA / VPN client'), color='purple'),
        Choice(HOME, _('Home or remote worker'), color='cyan'),
        Choice(CUSTOMER_SITE, _('At the customer site'), color='green'),
        Choice(INTERNET, _('Anywhere (internet)'), color='orange'),
    ]


class AccessMethodChoices(ChoiceSet):
    """How the last step reaches the target."""
    key = 'AccessPath.method'

    RDP = 'rdp'
    SSH = 'ssh'
    WEB = 'web'
    RMM = 'rmm'
    VENDOR_REMOTE = 'vendor_remote'
    VPN_NETWORK = 'vpn_network'
    CONSOLE = 'console'
    API = 'api'
    OTHER = 'other'

    CHOICES = [
        Choice(RDP, 'RDP', color='blue'),
        Choice(SSH, 'SSH', color='indigo'),
        Choice(WEB, _('Web portal'), color='cyan'),
        Choice(RMM, _('RMM agent'), color='teal'),
        Choice(VENDOR_REMOTE, _('Vendor remote tool'), color='orange'),
        Choice(VPN_NETWORK, _('VPN into the network'), color='red'),
        Choice(CONSOLE, _('Console'), color='purple'),
        Choice(API, 'API', color='gray'),
        Choice(OTHER, _('Other'), color='gray'),
    ]


class AuthenticationChoices(ChoiceSet):
    """How the person authenticates on the path."""
    key = 'AccessPath.authentication'

    SSO_MFA = 'sso_mfa'
    MFA = 'mfa'
    KEY = 'key'
    PASSWORD = 'password'
    SHARED_ACCOUNT = 'shared_account'
    UNKNOWN = 'unknown'

    CHOICES = [
        Choice(SSO_MFA, _('SSO with MFA'), color='green'),
        Choice(MFA, _('MFA'), color='green'),
        Choice(KEY, _('Key or certificate'), color='blue'),
        Choice(PASSWORD, _('Password only'), color='orange'),
        Choice(SHARED_ACCOUNT, _('Shared account'), color='red'),
        Choice(UNKNOWN, _('Unknown'), color='yellow'),
    ]

    # Values that count as "no MFA" in the review queue
    LACKS_MFA = (PASSWORD, SHARED_ACCOUNT, UNKNOWN)


class AccessPathStatusChoices(ChoiceSet):
    key = 'AccessPath.status'

    ACTIVE = 'active'
    PLANNED = 'planned'
    BREAK_GLASS = 'break_glass'
    DISABLED = 'disabled'

    CHOICES = [
        Choice(ACTIVE, _('Active'), color='green'),
        Choice(PLANNED, _('Planned'), color='cyan'),
        Choice(BREAK_GLASS, _('Break-glass'), color='red'),
        Choice(DISABLED, _('Disabled'), color='gray'),
    ]
