import datetime

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from dcim.models import Interface, Site
from ipam.models import IPAddress, Service
from tenancy.models import Contact, ContactGroup, Tenant
from utilities.testing import create_test_device, create_test_virtualmachine
from virtualization.models import VMInterface
from vpn.models import Tunnel

from netbox_access_paths import queries
from netbox_access_paths.choices import AccessPathStatusChoices
from netbox_access_paths.models import AccessHop, AccessPath, AccessRoute

TODAY = timezone.localdate()
DAY = datetime.timedelta(days=1)


class AccessRouteTest(TestCase):

    def test_str_and_unique_name(self):
        route = AccessRoute.objects.create(name='Office -> jump01', origin='office')
        self.assertEqual(str(route), 'Office -> jump01')
        self.assertEqual(route.get_origin_color(), 'blue')
        with self.assertRaises(ValidationError):
            AccessRoute(name='Office -> jump01', origin='home').full_clean()

    def test_route_with_paths_is_protected(self):
        route = AccessRoute.objects.create(name='Anywhere', origin='internet')
        AccessPath.objects.create(tenant=Tenant.objects.create(name='Acme', slug='acme'), route=route,
                                  target_url='https://portal.example.com', method='web')
        with self.assertRaises(ProtectedError):
            route.delete()


class AccessPathTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.site = Site.objects.create(name='Site 1', slug='site-1')
        cls.acme = Tenant.objects.create(name='Acme', slug='acme')
        cls.other = Tenant.objects.create(name='Other', slug='other')
        cls.route = AccessRoute.objects.create(name='Office -> jump01', origin='office')
        cls.dc01 = create_test_device('dc01', site=cls.site, tenant=cls.acme)
        cls.contact = Contact.objects.create(name='Jane at Acme')

    def path(self, **kwargs):
        kwargs.setdefault('tenant', self.acme)
        kwargs.setdefault('route', self.route)
        kwargs.setdefault('method', 'rdp')
        return AccessPath(**kwargs)

    def test_needs_target_or_url(self):
        with self.assertRaises(ValidationError):
            self.path().full_clean()
        self.path(target_url='https://portal.example.com', method='web').full_clean()
        self.path(target=self.dc01).full_clean()

    def test_target_type_is_limited(self):
        with self.assertRaises(ValidationError):
            self.path(target=self.site).full_clean()

    def test_target_must_exist(self):
        path = self.path(target_type=ContentType.objects.get_for_model(self.dc01), target_id=999999)
        with self.assertRaises(ValidationError):
            path.full_clean()

    def test_default_name(self):
        path = self.path(target=self.dc01)
        path.save()
        self.assertEqual(path.name, 'dc01 RDP')
        url_path = self.path(target_url='https://portal.example.com/admin', method='web')
        url_path.save()
        self.assertEqual(str(url_path), 'portal.example.com Web portal')

    def test_approval_is_dated(self):
        path = self.path(target=self.dc01, approved_by=self.contact)
        path.save()
        self.assertEqual(path.approved_on, TODAY)
        # An explicit date is kept
        path.approved_on = TODAY - 10 * DAY
        path.save()
        self.assertEqual(path.approved_on, TODAY - 10 * DAY)
        # A new approver without a new date is dated today
        path.approved_by = Contact.objects.create(name='John at Acme')
        path.save()
        self.assertEqual(path.approved_on, TODAY)

    def test_approval_not_in_future(self):
        with self.assertRaises(ValidationError):
            self.path(target=self.dc01, approved_on=TODAY + DAY).full_clean()

    def test_review_flags(self):
        path = self.path(target=self.dc01, authentication='password', expires=TODAY - DAY, review_by=TODAY)
        self.assertTrue(path.is_expired)
        self.assertTrue(path.is_review_due)
        self.assertTrue(path.lacks_mfa)
        path.status = AccessPathStatusChoices.DISABLED
        self.assertFalse(path.is_expired)
        self.assertFalse(path.is_review_due)
        self.assertFalse(self.path(target=self.dc01, authentication='sso_mfa').lacks_mfa)

    def test_tenant_mismatch(self):
        self.assertFalse(self.path(target=self.dc01).tenant_mismatch)
        self.assertTrue(self.path(tenant=self.other, target=self.dc01).tenant_mismatch)
        # A service takes its parent's tenant
        service = Service.objects.create(parent=self.dc01, name='rdp', port_mappings=['tcp/3389'])
        self.assertTrue(self.path(tenant=self.other, target=service).tenant_mismatch)
        # A target without a tenant is never a mismatch
        self.assertFalse(self.path(tenant=self.other, target=create_test_device('fw01', site=self.site))
                         .tenant_mismatch)

    def test_all_hops_route_first(self):
        AccessHop.objects.create(route=self.route, position=1, label='NetBird cloud')
        AccessHop.objects.create(route=self.route, position=2, device=create_test_device('jump01', site=self.site))
        path = self.path(target=self.dc01)
        path.save()
        AccessHop.objects.create(path=path, position=1, device=create_test_device('acme-fw', site=self.site))
        self.assertEqual([str(h.hop) for h in path.all_hops], ['NetBird cloud', 'jump01', 'acme-fw'])

    def test_deleted_target_leaves_the_path(self):
        device = create_test_device('old-dc', site=self.site)
        path = self.path(target=device)
        path.save()
        with_url = self.path(target=device, target_url='https://old-dc.example.com', method='web')
        with_url.save()
        device.delete()
        path.refresh_from_db()
        with_url.refresh_from_db()
        self.assertIsNone(path.target_type)
        self.assertTrue(path.is_target_missing)
        self.assertEqual(path.name, 'old-dc RDP')
        self.assertFalse(with_url.is_target_missing)
        self.assertIn(path, AccessPath.objects.filter(queries.target_missing_q()))


class AccessHopTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.route = AccessRoute.objects.create(name='Office -> jump01', origin='office')
        cls.path = AccessPath.objects.create(
            tenant=Tenant.objects.create(name='Acme', slug='acme'), route=cls.route,
            target_url='https://portal.example.com', method='web',
        )
        cls.device = create_test_device('jump01')

    def test_route_or_path(self):
        with self.assertRaises(ValidationError):
            AccessHop(route=self.route, path=self.path, position=1, label='x').full_clean()
        with self.assertRaises(ValidationError):
            AccessHop(position=1, label='x').full_clean()
        AccessHop(route=self.route, position=1, label='x').full_clean()
        AccessHop(path=self.path, position=1, label='x').full_clean()

    def test_route_or_path_in_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AccessHop.objects.create(position=1, label='x')

    def test_exactly_one_kind(self):
        with self.assertRaises(ValidationError):
            AccessHop(route=self.route, position=1).full_clean()
        with self.assertRaises(ValidationError):
            AccessHop(route=self.route, position=1, device=self.device, label='jump').full_clean()
        tunnel = Tunnel.objects.create(name='wg0', status='active', encapsulation='wireguard')
        AccessHop(route=self.route, position=1, tunnel=tunnel).full_clean()

    def test_position_unique_per_route_and_per_path(self):
        AccessHop.objects.create(route=self.route, position=1, device=self.device)
        with self.assertRaises(ValidationError):
            AccessHop(route=self.route, position=1, label='other').full_clean()
        # The same position on a path is fine
        AccessHop(path=self.path, position=1, label='customer firewall').full_clean()

    def test_str(self):
        hop = AccessHop.objects.create(route=self.route, position=2, device=self.device)
        self.assertEqual(str(hop), '2. jump01')
        self.assertEqual(hop.parent, self.route)


class QueriesTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        acme = Tenant.objects.create(name='Acme', slug='acme')
        cls.route = AccessRoute.objects.create(name='Office -> jump01', origin='office')
        cls.jump = create_test_device('jump01')
        AccessHop.objects.create(route=cls.route, position=1, device=cls.jump)
        cls.dc01 = create_test_device('dc01')
        iface = Interface.objects.create(device=cls.dc01, name='eth0', type='1000base-t')
        ip = IPAddress.objects.create(address='10.0.0.10/24', assigned_object=iface)
        service = Service.objects.create(parent=cls.dc01, name='rdp', port_mappings=['tcp/3389'])
        cls.vm = create_test_virtualmachine('vm01')
        vm_ip = IPAddress.objects.create(address='10.0.0.20/24',
                                         assigned_object=VMInterface.objects.create(virtual_machine=cls.vm, name='e0'))

        def path(name, **kwargs):
            return AccessPath.objects.create(name=name, tenant=acme, route=cls.route, method='rdp', **kwargs)

        cls.direct = path('direct', target=cls.dc01)
        cls.by_ip = path('by ip', target=ip)
        cls.by_service = path('by service', target=service)
        cls.vm_path = path('vm', target=vm_ip)
        cls.url_only = path('url', target_url='https://portal.example.com')
        cls.fw = create_test_device('acme-fw')
        AccessHop.objects.create(path=cls.url_only, position=1, device=cls.fw)

    def test_into_includes_services_and_addresses(self):
        into_dc = set(AccessPath.objects.filter(queries.into_q(devices=[self.dc01])))
        self.assertEqual(into_dc, {self.direct, self.by_ip, self.by_service})
        self.assertEqual(set(AccessPath.objects.filter(queries.into_q(virtual_machines=[self.vm]))), {self.vm_path})
        self.assertFalse(AccessPath.objects.filter(queries.into_q()).exists())

    def test_through_route_and_path_hops(self):
        through_jump = AccessPath.objects.filter(queries.through_q('device', [self.jump])).distinct()
        self.assertEqual(through_jump.count(), 5)
        through_fw = AccessPath.objects.filter(queries.through_q('device', [self.fw])).distinct()
        self.assertEqual(list(through_fw), [self.url_only])

    def test_held_by_groups_and_their_parents(self):
        support = ContactGroup.objects.create(name='Support', slug='support')
        tier2 = ContactGroup.objects.create(name='Tier 2', slug='tier-2', parent=support)
        jane = Contact.objects.create(name='Jane')
        jane.groups.add(tier2)
        bob = Contact.objects.create(name='Bob')
        self.direct.holders.add(bob)
        self.by_ip.holder_groups.add(support)
        self.by_service.holder_groups.add(tier2)
        held_by_jane = set(AccessPath.objects.filter(queries.held_by_q([jane])).distinct())
        self.assertEqual(held_by_jane, {self.by_ip, self.by_service})
        self.assertEqual(list(AccessPath.objects.filter(queries.held_by_q([bob])).distinct()), [self.direct])
