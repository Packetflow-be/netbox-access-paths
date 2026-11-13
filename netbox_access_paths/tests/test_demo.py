from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from dcim.models import Device
from tenancy.models import Contact, Tenant

from netbox_access_paths.models import AccessHop, AccessPath, AccessRoute
from netbox_access_paths.queries import needs_review_q


class DemoCommandTest(TestCase):

    def test_create_and_delete(self):
        call_command('access_paths_demo', stdout=StringIO())
        self.assertEqual(AccessRoute.objects.count(), 4)
        self.assertEqual(AccessPath.objects.count(), 9)
        self.assertTrue(AccessPath.objects.filter(needs_review_q()).exists())
        jump = Device.objects.get(name='msp-jump01')
        self.assertEqual(AccessPath.objects.filter(route__hops__device=jump).count(), 5)
        with self.assertRaises(CommandError):
            call_command('access_paths_demo', stdout=StringIO())

        call_command('access_paths_demo', '--delete', stdout=StringIO())
        for model in (AccessRoute, AccessPath, AccessHop, Device, Tenant, Contact):
            self.assertFalse(model.objects.exists(), model.__name__)
