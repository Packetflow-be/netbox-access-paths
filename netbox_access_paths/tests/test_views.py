import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from dcim.models import Device
from ipam.models import Prefix
from tenancy.models import Contact, ContactGroup, Tenant
from utilities.testing import TestCase, ViewTestCases, create_tags, create_test_device, create_test_virtualmachine

from netbox_access_paths.models import AccessHop, AccessPath, AccessRoute

TODAY = timezone.localdate()
DAY = datetime.timedelta(days=1)


class PluginURLMixin:
    def _get_base_url(self):
        return f'plugins:netbox_access_paths:{self.model._meta.model_name}_{{}}'


class AccessRouteViewTest(PluginURLMixin, ViewTestCases.PrimaryObjectViewTestCase):
    model = AccessRoute

    @classmethod
    def setUpTestData(cls):
        msp = Tenant.objects.create(name='MSP', slug='msp')
        prefix = Prefix.objects.create(prefix='10.0.10.0/24')
        AccessRoute.objects.bulk_create([
            AccessRoute(name='Route 1', origin='office', tenant=msp),
            AccessRoute(name='Route 2', origin='ztna', tenant=msp),
            AccessRoute(name='Route 3', origin='internet'),
        ])
        tags = create_tags('Alpha', 'Bravo', 'Charlie')
        cls.form_data = {
            'name': 'Office -> NetBird -> jump01',
            'origin': 'office',
            'origin_prefixes': [prefix.pk],
            'tenant': msp.pk,
            'description': 'The usual way',
            'tags': [t.pk for t in tags],
        }
        cls.csv_data = (
            'name,origin,origin_prefixes,tenant',
            'Route 4,office,10.0.10.0/24,MSP',
            'Route 5,home,,',
            'Route 6,customer_site,,MSP',
        )
        ids = list(AccessRoute.objects.order_by('pk').values_list('pk', flat=True))
        cls.csv_update_data = (
            'id,origin,description',
            f'{ids[0]},home,changed',
            f'{ids[1]},office,changed',
            f'{ids[2]},ztna,changed',
        )
        cls.bulk_edit_data = {
            'origin': 'customer_site',
        }


class AccessPathViewTest(PluginURLMixin, ViewTestCases.PrimaryObjectViewTestCase):
    model = AccessPath

    @classmethod
    def setUpTestData(cls):
        acme = Tenant.objects.create(name='Acme', slug='acme')
        route = AccessRoute.objects.create(name='Office', origin='office')
        dc01 = create_test_device('dc01', tenant=acme)
        create_test_virtualmachine('vm01')
        jane = Contact.objects.create(name='Jane')
        support = ContactGroup.objects.create(name='Support', slug='support')
        approver = Contact.objects.create(name='Acme IT manager')
        AccessPath.objects.bulk_create([
            AccessPath(name='Path 1', tenant=acme, route=route, target_url='https://a.example.com', method='web'),
            AccessPath(name='Path 2', tenant=acme, route=route, target_url='https://b.example.com', method='web'),
            AccessPath(name='Path 3', tenant=acme, route=route, target_url='https://c.example.com', method='web'),
        ])
        tags = create_tags('Alpha', 'Bravo', 'Charlie')
        cls.form_data = {
            'name': 'dc01 admin',
            'tenant': acme.pk,
            'route': route.pk,
            'target_content_type': ContentType.objects.get_for_model(Device).pk,
            'target_object_id': dc01.pk,
            'method': 'rdp',
            'holders': [jane.pk],
            'holder_groups': [support.pk],
            'authentication': 'mfa',
            'credential_ref': 'Vault: Acme/dc01 admin',
            'status': 'active',
            'approved_by': approver.pk,
            'approved_on': TODAY - 10 * DAY,
            'review_by': TODAY + 180 * DAY,
            'tags': [t.pk for t in tags],
        }
        cls.csv_data = (
            'tenant,route,target_type,target,target_url,method,holders,authentication',
            'Acme,Office,dcim.device,dc01,,rdp,Jane,mfa',
            'Acme,Office,virtualization.virtualmachine,vm01,,ssh,,key',
            'Acme,Office,,,https://portal.example.com,web,"Jane",',
            'Acme,Office,tenancy.tenant,Acme,,rmm,,mfa',
        )
        ids = list(AccessPath.objects.order_by('pk').values_list('pk', flat=True))
        cls.csv_update_data = (
            'id,status,description',
            f'{ids[0]},disabled,changed',
            f'{ids[1]},planned,changed',
            f'{ids[2]},break_glass,changed',
        )
        cls.bulk_edit_data = {
            'status': 'disabled',
            'review_by': TODAY + DAY,
        }


class AccessHopViewTest(PluginURLMixin, ViewTestCases.PrimaryObjectViewTestCase):
    model = AccessHop

    @classmethod
    def setUpTestData(cls):
        route = AccessRoute.objects.create(name='Office', origin='office')
        devices = [create_test_device(f'hop-{i}') for i in range(4)]
        for i in range(3):
            AccessHop.objects.create(route=route, position=i + 1, device=devices[i])
        tags = create_tags('Alpha', 'Bravo', 'Charlie')
        cls.form_data = {
            'route': route.pk,
            'position': 4,
            'device': devices[3].pk,
            'tags': [t.pk for t in tags],
        }
        cls.csv_data = (
            'route,position,device,label',
            'Office,5,hop-0,',
            'Office,6,,NetBird cloud',
            'Office,7,hop-2,',
        )
        ids = list(AccessHop.objects.order_by('pk').values_list('pk', flat=True))
        cls.csv_update_data = (
            'id,description',
            f'{ids[0]},office firewall',
            f'{ids[1]},ZTNA',
            f'{ids[2]},jump host',
        )
        cls.bulk_edit_data = {
            'description': 'changed',
        }


class AccessPathPagesTest(TestCase):
    """The pages people install the plugin for: tabs, chain, review queue, questionnaire export."""
    user_permissions = (
        'netbox_access_paths.view_accesspath', 'netbox_access_paths.view_accessroute',
        'netbox_access_paths.view_accesshop', 'tenancy.view_tenant', 'tenancy.view_contact',
        'dcim.view_device', 'virtualization.view_virtualmachine',
    )

    @classmethod
    def setUpTestData(cls):
        cls.acme = Tenant.objects.create(name='Acme', slug='acme')
        cls.globex = Tenant.objects.create(name='Globex', slug='globex')
        cls.jump = create_test_device('jump01')
        cls.route = AccessRoute.objects.create(name='Office -> jump01', origin='office')
        AccessHop.objects.create(route=cls.route, position=1, label='NetBird cloud')
        AccessHop.objects.create(route=cls.route, position=2, device=cls.jump)
        cls.dc01 = create_test_device('dc01', tenant=cls.acme)
        cls.vm = create_test_virtualmachine('globex-app')
        cls.fw = create_test_device('acme-fw')
        cls.jane = Contact.objects.create(name='Jane')
        cls.path = AccessPath.objects.create(
            name='dc01 admin', tenant=cls.acme, route=cls.route, target=cls.dc01, method='rdp',
            authentication='password', credential_ref='Vault: Acme/dc01', review_by=TODAY - DAY,
        )
        cls.path.holders.add(cls.jane)
        AccessHop.objects.create(path=cls.path, position=1, device=cls.fw)
        AccessPath.objects.create(
            name='globex app', tenant=cls.globex, route=cls.route, target=cls.vm, method='ssh',
            authentication='key', expires=TODAY - DAY,
        )
        AccessPath.objects.create(
            name='m365 admin', tenant=cls.acme, route=cls.route, target_url='https://admin.microsoft.com',
            method='web', authentication='sso_mfa', status='break_glass',
        )

    @override_settings(EXEMPT_VIEW_PERMISSIONS=[])
    def test_path_detail_draws_the_chain(self):
        response = self.client.get(self.path.get_absolute_url())
        self.assertHttpStatus(response, 200)
        for text in ('Office network', 'NetBird cloud', 'jump01', 'Customer side', 'acme-fw', 'RDP', 'dc01',
                     'no MFA', 'review due'):
            self.assertContains(response, text)

    @override_settings(EXEMPT_VIEW_PERMISSIONS=[])
    def test_route_detail(self):
        response = self.client.get(self.route.get_absolute_url())
        self.assertHttpStatus(response, 200)
        self.assertContains(response, '3 paths')

    @override_settings(EXEMPT_VIEW_PERMISSIONS=[])
    def test_tenant_tab(self):
        response = self.client.get(reverse('tenancy:tenant_access_paths', kwargs={'pk': self.acme.pk}))
        self.assertHttpStatus(response, 200)
        self.assertContains(response, 'dc01 admin')
        self.assertContains(response, 'm365 admin')
        self.assertNotContains(response, 'globex app')
        self.assertContains(response, 'Questionnaire (CSV)')

    @override_settings(EXEMPT_VIEW_PERMISSIONS=[])
    def test_contact_tab(self):
        response = self.client.get(reverse('tenancy:contact_access_paths', kwargs={'pk': self.jane.pk}))
        self.assertHttpStatus(response, 200)
        self.assertContains(response, 'dc01 admin')
        self.assertNotContains(response, 'm365 admin')

    @override_settings(EXEMPT_VIEW_PERMISSIONS=[])
    def test_device_tab_through_and_into(self):
        # jump01 is on the route every path uses: the blast radius covers both customers
        response = self.client.get(reverse('dcim:device_access_paths', kwargs={'pk': self.jump.pk}))
        self.assertHttpStatus(response, 200)
        for text in ('dc01 admin', 'globex app', 'm365 admin', 'into 2 customers'):
            self.assertContains(response, text)
        response = self.client.get(reverse('dcim:device_access_paths', kwargs={'pk': self.dc01.pk}))
        self.assertContains(response, 'dc01 admin')
        self.assertContains(response, 'No access path runs through it.')

    @override_settings(EXEMPT_VIEW_PERMISSIONS=[])
    def test_virtual_machine_tab(self):
        response = self.client.get(reverse('virtualization:virtualmachine_access_paths', kwargs={'pk': self.vm.pk}))
        self.assertHttpStatus(response, 200)
        self.assertContains(response, 'globex app')

    @override_settings(EXEMPT_VIEW_PERMISSIONS=[])
    def test_review_queue(self):
        response = self.client.get(reverse('plugins:netbox_access_paths:review'))
        self.assertHttpStatus(response, 200)
        for text in ('dc01 admin', 'globex app', 'm365 admin', '3 access paths need a person'):
            self.assertContains(response, text)
        response = self.client.get(reverse('plugins:netbox_access_paths:review') + f'?tenant_id={self.globex.pk}')
        self.assertContains(response, 'globex app')
        self.assertNotContains(response, 'dc01 admin')

    @override_settings(EXEMPT_VIEW_PERMISSIONS=[])
    def test_review_queue_requires_permission(self):
        self.user.object_permissions.all().delete()
        self.user._perm_cache = None
        response = self.client.get(reverse('plugins:netbox_access_paths:review'))
        self.assertIn(response.status_code, (302, 403))

    @override_settings(EXEMPT_VIEW_PERMISSIONS=[])
    def test_export_csv(self):
        response = self.client.get(reverse('plugins:netbox_access_paths:export') + f'?tenant_id={self.acme.pk}')
        self.assertHttpStatus(response, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('access-paths-acme-', response['Content-Disposition'])
        body = response.content.decode()
        self.assertIn('NetBird cloud -> jump01 -> acme-fw', body)
        self.assertIn('https://admin.microsoft.com', body)
        self.assertNotIn('globex', body)
        # The credential reference stays out unless the plugin setting asks for it
        self.assertNotIn('Vault: Acme', body)

    @override_settings(EXEMPT_VIEW_PERMISSIONS=[],
                       PLUGINS_CONFIG={'netbox_access_paths': {'export_credential_ref': True}})
    def test_export_markdown_with_credential_ref(self):
        url = reverse('plugins:netbox_access_paths:export') + f'?tenant_id={self.acme.pk}&format=markdown'
        response = self.client.get(url)
        self.assertHttpStatus(response, 200)
        body = response.content.decode()
        self.assertTrue(body.startswith('# Access paths: Acme'))
        self.assertIn('| dc01 admin |', body)
        self.assertIn('Vault: Acme/dc01', body)

    @override_settings(EXEMPT_VIEW_PERMISSIONS=[])
    def test_export_unknown_format(self):
        response = self.client.get(reverse('plugins:netbox_access_paths:export') + '?format=xlsx')
        self.assertHttpStatus(response, 400)
