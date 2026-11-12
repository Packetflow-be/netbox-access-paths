from django.urls import reverse
from rest_framework import status

from dcim.models import Site
from ipam.models import Prefix, Service
from tenancy.models import Contact, ContactGroup, Tenant
from utilities.testing import APITestCase, APIViewTestCases, create_test_device, create_test_virtualmachine
from vpn.models import Tunnel

from netbox_access_paths.models import AccessHop, AccessPath, AccessRoute

RELATED_VIEW = (
    'tenancy.view_tenant', 'tenancy.view_contact', 'tenancy.view_contactgroup', 'ipam.view_prefix',
    'ipam.view_service', 'dcim.view_device', 'virtualization.view_virtualmachine', 'vpn.view_tunnel',
    'netbox_access_paths.view_accessroute', 'netbox_access_paths.view_accesspath',
)


class AccessRouteAPITest(APIViewTestCases.APIViewTestCase):
    model = AccessRoute
    view_namespace = 'plugins-api:netbox_access_paths'
    graphql_base_name = 'access_paths_route'
    user_permissions = RELATED_VIEW
    brief_fields = ['description', 'display', 'id', 'name', 'origin', 'url']
    bulk_update_data = {
        'origin': 'home',
        'description': 'New description',
    }
    bulk_update_invalid_data = {
        'origin': 'moon',
    }

    @classmethod
    def setUpTestData(cls):
        msp = Tenant.objects.create(name='MSP', slug='msp')
        prefix = Prefix.objects.create(prefix='10.0.10.0/24')
        AccessRoute.objects.bulk_create([
            AccessRoute(name='Route 1', origin='office', tenant=msp),
            AccessRoute(name='Route 2', origin='ztna'),
            AccessRoute(name='Route 3', origin='internet'),
        ])
        cls.create_data = [
            {'name': 'Route 4', 'origin': 'office', 'tenant': msp.pk, 'origin_prefixes': [prefix.pk]},
            {'name': 'Route 5', 'origin': 'home'},
            {'name': 'Route 6', 'origin': 'customer_site', 'description': 'On site at the customer'},
        ]


class AccessPathAPITest(APIViewTestCases.APIViewTestCase):
    model = AccessPath
    view_namespace = 'plugins-api:netbox_access_paths'
    graphql_base_name = 'access_paths_path'
    user_permissions = RELATED_VIEW
    brief_fields = ['description', 'display', 'id', 'method', 'name', 'status', 'url']
    bulk_update_data = {
        'status': 'disabled',
        'authentication': 'mfa',
    }
    bulk_update_invalid_data = {
        'method': 'telepathy',
    }

    @classmethod
    def setUpTestData(cls):
        acme = Tenant.objects.create(name='Acme', slug='acme')
        route = AccessRoute.objects.create(name='Office', origin='office')
        dc01 = create_test_device('dc01', tenant=acme)
        service = Service.objects.create(parent=dc01, name='rdp', port_mappings=['tcp/3389'])
        jane = Contact.objects.create(name='Jane')
        support = ContactGroup.objects.create(name='Support', slug='support')
        AccessPath.objects.bulk_create([
            AccessPath(name='Path 1', tenant=acme, route=route, target_url='https://a.example.com', method='web'),
            AccessPath(name='Path 2', tenant=acme, route=route, target_url='https://b.example.com', method='web'),
            AccessPath(name='Path 3', tenant=acme, route=route, target_url='https://c.example.com', method='web'),
        ])
        cls.create_data = [
            {'tenant': acme.pk, 'route': route.pk, 'target_type': 'dcim.device', 'target_id': dc01.pk,
             'method': 'rdp', 'holders': [jane.pk], 'holder_groups': [support.pk], 'authentication': 'mfa'},
            {'name': 'Portal', 'tenant': acme.pk, 'route': route.pk, 'target_url': 'https://portal.example.com',
             'method': 'web', 'credential_ref': 'Vault: Acme/portal'},
            {'tenant': acme.pk, 'route': route.pk, 'target_type': 'ipam.service', 'target_id': service.pk,
             'method': 'rdp', 'status': 'break_glass', 'approved_by': jane.pk},
        ]


class AccessHopAPITest(APIViewTestCases.APIViewTestCase):
    model = AccessHop
    view_namespace = 'plugins-api:netbox_access_paths'
    graphql_base_name = 'access_paths_hop'
    user_permissions = RELATED_VIEW
    brief_fields = ['description', 'display', 'id', 'label', 'position', 'url']
    bulk_update_data = {
        'description': 'New description',
    }

    @classmethod
    def setUpTestData(cls):
        route = AccessRoute.objects.create(name='Office', origin='office')
        path = AccessPath.objects.create(tenant=Tenant.objects.create(name='Acme', slug='acme'), route=route,
                                         target_url='https://a.example.com', method='web')
        site = Site.objects.create(name='Site 1', slug='site-1')
        devices = [create_test_device(f'hop-{i}', site=site) for i in range(3)]
        for i in range(3):
            AccessHop.objects.create(route=route, position=i + 1, device=devices[i])
        tunnel = Tunnel.objects.create(name='wg0', status='active', encapsulation='wireguard')
        cls.create_data = [
            {'route': route.pk, 'position': 4, 'label': 'NetBird cloud'},
            {'path': path.pk, 'position': 1, 'tunnel': tunnel.pk},
            {'path': path.pk, 'position': 2, 'virtual_machine': create_test_virtualmachine('jump02').pk},
        ]


class AccessPathAPIBehaviourTest(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.acme = Tenant.objects.create(name='Acme', slug='acme')
        cls.route = AccessRoute.objects.create(name='Office', origin='office')
        AccessHop.objects.create(route=cls.route, position=1, label='NetBird cloud')
        cls.dc01 = create_test_device('dc01')
        cls.path = AccessPath.objects.create(tenant=cls.acme, route=cls.route, target=cls.dc01, method='rdp')
        AccessHop.objects.create(path=cls.path, position=1, device=create_test_device('acme-fw'))

    def setUp(self):
        super().setUp()
        self.add_permissions('netbox_access_paths.view_accesspath', 'netbox_access_paths.add_accesspath',
                             'tenancy.view_tenant', 'netbox_access_paths.view_accessroute', 'dcim.view_device')

    def test_chain_and_target(self):
        url = reverse('plugins-api:netbox_access_paths-api:accesspath-detail', kwargs={'pk': self.path.pk})
        response = self.client.get(url, **self.header)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertEqual([(h['side'], h['name']) for h in response.data['chain']],
                         [('route', 'NetBird cloud'), ('path', 'acme-fw')])
        self.assertEqual(response.data['target']['name'], 'dc01')
        self.assertEqual(response.data['name'], 'dc01 RDP')

    def test_target_type_is_limited(self):
        url = reverse('plugins-api:netbox_access_paths-api:accesspath-list')
        data = {'tenant': self.acme.pk, 'route': self.route.pk, 'target_type': 'dcim.site', 'target_id': 1,
                'method': 'rdp'}
        response = self.client.post(url, data, format='json', **self.header)
        self.assertHttpStatus(response, status.HTTP_400_BAD_REQUEST)

    def test_needs_a_target(self):
        url = reverse('plugins-api:netbox_access_paths-api:accesspath-list')
        data = {'tenant': self.acme.pk, 'route': self.route.pk, 'method': 'rdp'}
        response = self.client.post(url, data, format='json', **self.header)
        self.assertHttpStatus(response, status.HTTP_400_BAD_REQUEST)
