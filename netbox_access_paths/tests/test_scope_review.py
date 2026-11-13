import datetime

from django.core.exceptions import ValidationError
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import ObjectChange
from dcim.models import Interface, Site
from ipam.models import VLAN, VRF, IPAddress, Prefix
from tenancy.models import Tenant
from utilities.testing import TestCase, create_test_device, create_test_virtualmachine
from virtualization.models import Cluster, VMInterface

from netbox_access_paths import export, queries
from netbox_access_paths.models import AccessPath, AccessRoute
from netbox_access_paths.widgets import AccessReviewWidget

TODAY = timezone.localdate()
DAY = datetime.timedelta(days=1)
NO_SAME_TENANT = {'netbox_access_paths': {'scope_same_tenant': False}}


def into(device=None, vm=None):
    q = queries.into_q(devices=[device]) if device else queries.into_q(virtual_machines=[vm])
    return set(AccessPath.objects.filter(q))


class ScopeTargetTest(TestCase):
    """A path into a prefix, VLAN, cluster, site or tenant covers the devices and VMs in it."""

    @classmethod
    def setUpTestData(cls):
        cls.acme = Tenant.objects.create(name='Acme', slug='acme')
        cls.globex = Tenant.objects.create(name='Globex', slug='globex')
        cls.route = AccessRoute.objects.create(name='Office', origin='office')
        cls.site = Site.objects.create(name='Acme HQ', slug='acme-hq', tenant=cls.acme)
        cls.other_site = Site.objects.create(name='Elsewhere', slug='elsewhere')
        cls.vlan = VLAN.objects.create(name='Servers', vid=20)
        cls.prefix = Prefix.objects.create(prefix='192.168.1.0/24', vlan=cls.vlan)
        cls.vrf = VRF.objects.create(name='Other')
        cls.vrf_prefix = Prefix.objects.create(prefix='192.168.1.0/24', vrf=cls.vrf)

        # Acme's server, a server without a tenant and Globex's server: all at the site, all in 192.168.1.0/24
        cls.acme_srv = create_test_device('acme-srv', site=cls.site, tenant=cls.acme)
        cls.shared_srv = create_test_device('shared-srv', site=cls.site)
        cls.globex_srv = create_test_device('globex-srv', site=cls.site, tenant=cls.globex)
        for n, device in enumerate((cls.acme_srv, cls.shared_srv, cls.globex_srv), start=10):
            iface = Interface.objects.create(device=device, name='eth0', type='1000base-t')
            IPAddress.objects.create(address=f'192.168.1.{n}/24', assigned_object=iface)
        cls.away = create_test_device('away', site=cls.other_site, tenant=cls.acme)
        cls.tagged = create_test_device('tagged', site=cls.other_site)
        Interface.objects.create(device=cls.tagged, name='eth0', type='1000base-t', mode='access',
                                 untagged_vlan=cls.vlan)
        cls.vm = create_test_virtualmachine('acme-vm')
        cls.cluster = Cluster.objects.get(name='Cluster 1')
        VMInterface.objects.create(virtual_machine=cls.vm, name='eth0')

        def path(name, target, tenant=cls.acme):
            return AccessPath.objects.create(name=name, tenant=tenant, route=cls.route, method='vpn_network',
                                             target=target)

        cls.site_path = path('site', cls.site)
        cls.prefix_path = path('prefix', cls.prefix)
        cls.vrf_prefix_path = path('vrf prefix', cls.vrf_prefix)
        cls.vlan_path = path('vlan', cls.vlan)
        cls.cluster_path = path('cluster', cls.cluster)
        cls.tenant_path = path('tenant', cls.acme)

    def test_is_scope_and_names(self):
        self.assertTrue(self.site_path.is_scope)
        self.assertTrue(self.tenant_path.is_scope)
        self.assertEqual(self.prefix_path.target_label, '192.168.1.0/24')
        self.assertEqual(AccessPath(tenant=self.acme, route=self.route, method='vpn_network',
                                    target=self.site).default_name(), 'Acme HQ VPN into the network')
        direct = AccessPath.objects.create(tenant=self.acme, route=self.route, method='rdp', target=self.acme_srv)
        self.assertFalse(direct.is_scope)
        self.assertFalse(AccessPath(tenant=self.acme, route=self.route, method='web',
                                    target_url='https://x.example.com').is_scope)

    def test_tenant_target_mismatch(self):
        self.assertFalse(self.tenant_path.tenant_mismatch)
        other = AccessPath(tenant=self.globex, route=self.route, method='rmm', target=self.acme)
        self.assertTrue(other.tenant_mismatch)

    def test_device_of_the_tenant_is_covered(self):
        self.assertEqual(into(self.acme_srv), {self.site_path, self.prefix_path, self.vlan_path, self.tenant_path})

    def test_device_without_tenant_is_covered_except_by_the_tenant_path(self):
        self.assertEqual(into(self.shared_srv), {self.site_path, self.prefix_path, self.vlan_path})

    def test_other_tenants_device_is_not_covered(self):
        # Customers share sites, clusters and address space: Acme's paths don't lead into Globex's server
        self.assertEqual(into(self.globex_srv), set())

    @override_settings(PLUGINS_CONFIG=NO_SAME_TENANT)
    def test_scope_same_tenant_off(self):
        self.assertEqual(into(self.globex_srv), {self.site_path, self.prefix_path, self.vlan_path})

    def test_prefix_needs_the_same_vrf(self):
        self.assertNotIn(self.vrf_prefix_path, into(self.acme_srv))
        iface = self.away.interfaces.create(name='eth0', type='1000base-t')
        IPAddress.objects.create(address='192.168.1.50/24', vrf=self.vrf, assigned_object=iface)
        self.assertEqual(into(self.away), {self.vrf_prefix_path, self.tenant_path})

    def test_vlan_on_an_interface(self):
        self.assertEqual(into(self.tagged), {self.vlan_path})

    def test_cluster_covers_its_virtual_machines(self):
        self.assertEqual(into(vm=self.vm), {self.cluster_path})

    def test_scopes_can_be_left_out(self):
        q = queries.into_q(devices=[self.acme_srv], scopes=False)
        self.assertFalse(AccessPath.objects.filter(q).exists())

    def test_into_takes_primary_keys(self):
        q = queries.into_q(devices=[self.acme_srv.pk])
        self.assertIn(self.site_path, AccessPath.objects.filter(q))

    def test_deleted_scope_leaves_the_path(self):
        self.vrf_prefix.delete()
        self.vrf_prefix_path.refresh_from_db()
        self.assertTrue(self.vrf_prefix_path.is_target_missing)

    def test_other_models_are_refused(self):
        with self.assertRaises(ValidationError):
            AccessPath(tenant=self.acme, route=self.route, method='rdp', target=self.vrf).full_clean()

    def test_export_says_everything_in(self):
        rows = export.build_rows([self.site_path])
        self.assertEqual(rows[0]['target'], 'everything in site Acme HQ')

    @override_settings(EXEMPT_VIEW_PERMISSIONS=['*'])
    def test_device_tab_lists_scope_paths(self):
        self.add_permissions('netbox_access_paths.view_accesspath', 'dcim.view_device')
        response = self.client.get(reverse('dcim:device_access_paths', kwargs={'pk': self.acme_srv.pk}))
        self.assertHttpStatus(response, 200)
        self.assertContains(response, 'everything in')
        self.assertContains(response, 'Acme HQ')

    def test_filter_and_import_by_name(self):
        self.add_permissions('netbox_access_paths.view_accesspath', 'netbox_access_paths.add_accesspath')
        url = reverse('plugins-api:netbox_access_paths-api:accesspath-list')
        self.client.force_login(self.user)
        response = self.client.get(f'{url}?device_id={self.acme_srv.pk}')
        self.assertEqual(response.json()['count'], 4)
        self.assertTrue(all(row['scope'] for row in response.json()['results']))


class ReviewSignOffTest(TestCase):
    user_permissions = ('netbox_access_paths.view_accesspath', 'netbox_access_paths.change_accesspath')

    @classmethod
    def setUpTestData(cls):
        acme = Tenant.objects.create(name='Acme', slug='acme')
        globex = Tenant.objects.create(name='Globex', slug='globex')
        route = AccessRoute.objects.create(name='Office', origin='office')
        cls.due = AccessPath.objects.create(name='due', tenant=acme, route=route, method='web',
                                            target_url='https://a.example.com', authentication='mfa',
                                            review_by=TODAY - DAY)
        cls.other = AccessPath.objects.create(name='other', tenant=globex, route=route, method='web',
                                              target_url='https://b.example.com', authentication='mfa',
                                              review_by=TODAY - 2 * DAY)
        cls.url = reverse('plugins:netbox_access_paths:accesspath_mark_reviewed')

    def test_mark_reviewed_sets_the_dates(self):
        path = AccessPath.objects.get(pk=self.due.pk)
        path.mark_reviewed(self.user)
        self.assertEqual(path.reviewed_on, TODAY)
        self.assertEqual(path.reviewed_by, self.user)
        self.assertEqual(path.review_by, TODAY + 365 * DAY)
        self.assertFalse(path.is_review_due)

    def test_review_date_not_in_the_future(self):
        path = AccessPath.objects.get(pk=self.due.pk)
        path.reviewed_on = TODAY + DAY
        with self.assertRaises(ValidationError):
            path.full_clean()

    @override_settings(PLUGINS_CONFIG={'netbox_access_paths': {'review_interval_days': 90}})
    def test_post_one_path(self):
        response = self.client.post(self.url, {'pk': self.due.pk, 'return_url': self.due.get_absolute_url()})
        self.assertRedirects(response, self.due.get_absolute_url(), fetch_redirect_response=False)
        self.due.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual((self.due.reviewed_on, self.due.reviewed_by), (TODAY, self.user))
        self.assertEqual(self.due.review_by, TODAY + 90 * DAY)
        self.assertIsNone(self.other.reviewed_on)
        self.assertTrue(ObjectChange.objects.filter(changed_object_id=self.due.pk, action='update').exists())

    def test_post_all_matching_the_filters(self):
        response = self.client.post(f'{self.url}?tenant_id={self.other.tenant_id}', {'_all': 'on'})
        self.assertHttpStatus(response, 302)
        self.due.refresh_from_db()
        self.other.refresh_from_db()
        self.assertIsNone(self.due.reviewed_on)
        self.assertEqual(self.other.reviewed_on, TODAY)

    def test_post_nothing_and_unsafe_return_url(self):
        response = self.client.post(self.url, {'return_url': 'https://evil.example.com/'})
        self.assertRedirects(response, reverse('plugins:netbox_access_paths:accesspath_list'),
                             fetch_redirect_response=False)
        self.due.refresh_from_db()
        self.assertIsNone(self.due.reviewed_on)

    def test_get_is_not_allowed(self):
        self.assertHttpStatus(self.client.get(self.url), 405)

    @override_settings(EXEMPT_VIEW_PERMISSIONS=[])
    def test_needs_change_permission(self):
        self.remove_permissions('netbox_access_paths.change_accesspath')
        response = self.client.post(self.url, {'pk': self.due.pk})
        self.assertIn(response.status_code, (302, 403))
        self.due.refresh_from_db()
        self.assertIsNone(self.due.reviewed_on)
        # ... and no button on the pages
        self.assertNotContains(self.client.get(self.due.get_absolute_url()), 'Mark reviewed')
        self.assertNotContains(self.client.get(reverse('plugins:netbox_access_paths:review')), 'Mark reviewed')

    @override_settings(EXEMPT_VIEW_PERMISSIONS=[])
    def test_buttons(self):
        self.assertContains(self.client.get(self.due.get_absolute_url()), 'Mark reviewed')
        self.assertContains(self.client.get(reverse('plugins:netbox_access_paths:review')), 'Mark reviewed')
        self.add_permissions('netbox_access_paths.delete_accesspath')
        response = self.client.get(reverse('plugins:netbox_access_paths:accesspath_list'))
        self.assertContains(response, 'Mark Reviewed')
        self.assertContains(response, self.url)

    def test_detail_shows_the_reviewer(self):
        self.client.post(self.url, {'pk': self.due.pk})
        response = self.client.get(self.due.get_absolute_url())
        self.assertContains(response, 'Last reviewed')
        self.assertContains(response, self.user.username)

    def test_export_has_last_reviewed(self):
        self.client.post(self.url, {'pk': self.due.pk})
        body = self.client.get(reverse('plugins:netbox_access_paths:export') + '?name=due').content.decode()
        self.assertIn('Last reviewed', body)
        self.assertIn(TODAY.isoformat(), body)


class AccessReviewWidgetTest(TestCase):
    user_permissions = ('netbox_access_paths.view_accesspath',)

    @classmethod
    def setUpTestData(cls):
        acme = Tenant.objects.create(name='Acme', slug='acme')
        route = AccessRoute.objects.create(name='Office', origin='office')
        AccessPath.objects.create(name='due', tenant=acme, route=route, method='web', authentication='mfa',
                                  target_url='https://a.example.com', review_by=TODAY - DAY)
        AccessPath.objects.create(name='no mfa', tenant=acme, route=route, method='web',
                                  target_url='https://b.example.com', authentication='password')

    def _render(self):
        request = RequestFactory().get('/')
        request.user = self.user
        return AccessReviewWidget().render(request)

    @override_settings(EXEMPT_VIEW_PERMISSIONS=[])
    def test_counts_and_links(self):
        html = self._render()
        for text in ('Review due', 'Without MFA', 'Expired', '?review_due=true', 'Open the review queue'):
            self.assertIn(text, html)
        self.assertEqual(html.count('text-bg-warning'), 2)
        self.assertEqual(html.count('text-bg-success'), 3)

    @override_settings(EXEMPT_VIEW_PERMISSIONS=[])
    def test_without_permission(self):
        self.remove_permissions('netbox_access_paths.view_accesspath')
        html = self._render()
        self.assertIn('No permission', html)
        self.assertNotIn('Review due', html)

    def test_registered(self):
        from netbox.registry import registry
        self.assertIn('netbox_access_paths.AccessReviewWidget', registry['widgets'])
