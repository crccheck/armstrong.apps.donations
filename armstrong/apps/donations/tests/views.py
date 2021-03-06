from armstrong.dev.tests.utils.backports import override_settings
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.test.client import Client
from functools import wraps
import fudge
import os
import random

from ._utils import TestCase

from .. import constants
from .. import forms
from .. import models
from .. import views


def failed_purchase(func):
    def inner(self):
        random_text = "Some Random Text (%d)" % random.randint(1000, 2000)
        backend = self.get_backend_stub(successful=False, reason=random_text)
        self.patches = [
            fudge.patch_object(views, "backends", backend),
        ]
        fudge.clear_calls()

        data = self.random_post_data
        response = self.client.post(self.url, data)
        backend_response = backend.get_backend().purchase()["response"]
        func(self, response, random_text=random_text,
                backend_response=backend_response)
    return inner


class BaseDonationFormViewTestCase(TestCase):
    view_class = views.DonationFormView
    view_name = "donations_form"

    @property
    def url(self):
        # TODO: move this into armstrong.dev
        return reverse(self.view_name)

    def setUp(self):
        super(BaseDonationFormViewTestCase, self).setUp()
        # TODO: move this to armstrong.dev
        self.client = Client()

        # TODO: make this based off of class name and move into armstrong.dev
        settings.TEMPLATE_DIRS = (
            os.path.join(os.path.dirname(__file__), "_templates"),
        )
        self.client
        self.patches = [
            fudge.patch_object(views, "backends", self.get_backend_stub())
        ]
        fudge.clear_calls()

    def tearDown(self):
        super(BaseDonationFormViewTestCase, self).tearDown()

    def assert_in_context(self, response, name):
        # TODO: move this into armstrong.dev
        context = (response.context if hasattr(response, "context")
                else response.context_data)
        self.assertTrue(name in context,
                msg="%s was not in the context" % name)

    def assert_type_in_context(self, response, name, expected_type):
        self.assert_in_context(response, name)
        context = (response.context if hasattr(response, "context")
                else response.context_data)
        self.assertTrue(isinstance(context[name], expected_type),
                msg="%s in the context, but does not have a class of %s" % (
                        name, expected_type.__name__))

    def assert_value_in_context(self, response, name, expected_value):
        self.assert_in_context(response, name)
        context = (response.context if hasattr(response, "context")
                else response.context_data)
        self.assertEqual(context[name], expected_value,
                msg="%s in the context, but not equal to '%s'" % (
                        name, expected_value))

    def assert_template(self, template, response):
        template_names = [a.name for a in response.templates]
        self.assertTrue(template in template_names,
                msg="%s not found in templates: %s" % (
                        template, response.templates))

    def assert_form_has_errors(self, response, form_name, error_fields=None):
        self.assert_in_context(response, form_name)
        form = response.context[form_name]
        self.assertNotEqual(form.errors, [],
                msg="%s.errors was empty?" % form_name)
        if error_fields:
            for field in error_fields:
                self.assertTrue(field in form.errors,
                        msg="%s not in the errors" % field)

    def assert_subform_has_errors(self, response, subform_name,
            error_fields=None):
        form = response.context["donation_form"]
        self.assertTrue(hasattr(form, subform_name))
        subform = getattr(form, subform_name)
        if error_fields:
            for field in error_fields:
                self.assertTrue(field in subform.errors,
                        msg="%s not in the errors" % field)

    def get_view_object(self):
        view = self.view_class()
        view.request = self.factory.get(self.url)
        return view

    def get_response(self):
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code, msg="sanity check")
        return response

    def get_fake_post_request(self, confirmed=False):
        d = {} if not confirmed else {"confirmed": u"1"}
        return self.factory.post(self.url, d)

    @property
    def fake_get_request(self):
        return self.factory.get(self.url)

    def get_post_view(self, confirmed=False):
        v = views.DonationFormView(confirm=True)
        v.request = self.get_fake_post_request(confirmed=confirmed)
        return v

    post_view = property(get_post_view)


# TODO: move to armstrong.dev
def get_response(func):
    @wraps(func)
    def inner(self):
        func(self, self.get_response())
    return inner


class DonationFormViewGetTestCase(BaseDonationFormViewTestCase):
    @get_response
    def test_adds_form_action_url_to_context(self, response):
        self.assert_value_in_context(response, "form_action_url", "")

    @get_response
    def test_adds_donation_formset_to_context(self, response):
        self.assert_type_in_context(response, "donation_form",
                forms.BaseDonationForm)

    def test_get_donation_form_returns_credit_card_form_by_default(self):
        # TODO: make sure in "default" state
        view = self.get_view_object()
        donation_form = view.get_donation_form()
        self.assertIsA(donation_form, forms.CreditCardDonationForm)

    def test_get_context_turns_kwargs_into_params(self):
        r = lambda: random.randint(100, 200)
        random_kwargs = {
            "slug%d" % r(): "foo-%d" % r(),
        }
        view = self.get_view_object()
        context = view.get_context_data(**random_kwargs)
        self.assertEqual(len(context["params"]), len(random_kwargs),
                msg="verify context.params is the same length")
        for key in context["params"].keys():
            self.assert_(key in random_kwargs)

    def test_form_is_invalid_passes_kwargs_to_get_context_data(self):
        r = lambda: random.randint(100, 200)
        random_kwargs = {
            "slug%d" % r(): "foo-%d" % r(),
        }

        get_context_data = fudge.Fake()
        get_context_data.expects_call().with_args(**random_kwargs)

        view = self.post_view
        with fudge.patched_context(view, "get_context_data", get_context_data):
            view.post({}, **random_kwargs)

        fudge.verify()

    def test_form_is_valid_passes_kwargs_to_get_context_data(self):
        donation, donation_form = self.random_donation_and_form
        r = lambda: random.randint(100, 200)
        random_kwargs = {
            "slug%d" % r(): "foo-%d" % r(),
        }

        get_context_data = fudge.Fake()
        get_context_data.expects_call().with_args(**random_kwargs)

        view = self.post_view
        with fudge.patched_context(view, "get_context_data", get_context_data):
            view.form_is_valid(donation_form, **random_kwargs)

        fudge.verify()

    def test_form_is_valid_passes_kwargs_to_purchase_failed(self):
        donation, donation_form = self.random_donation_and_form
        r = lambda: random.randint(100, 200)
        random_kwargs = {
            "slug%d" % r(): "foo-%d" % r(),
        }

        view = self.post_view
        view.confirm = False
        backends = self.get_backend_stub(successful=False)
        backend_response = backends.get_backend().purchase()

        purchase_failed = fudge.Fake()
        purchase_failed.expects_call().with_args(backend_response,
                **random_kwargs)

        with fudge.patched_context(views, "backends", backends):
            with fudge.patched_context(view, "purchase_failed",
                    purchase_failed):
                view.form_is_valid(donation_form, **random_kwargs)

        fudge.verify()

    def test_purchase_failed_passes_kwargs_to_get_context_data(self):
        backend_response = {
            "reason": "Some Random Reason",
            "response": "Some Random Response",
        }
        r = lambda: random.randint(100, 200)
        random_kwargs = {
            "slug%d" % r(): "foo-%d" % r(),
        }

        get_context_data = fudge.Fake()
        (get_context_data.expects_call()
                .with_args(**random_kwargs)
                .returns({}))

        view = self.post_view
        with fudge.patched_context(view, "get_context_data", get_context_data):
            view.purchase_failed(backend_response, **random_kwargs)

        fudge.verify()


def form_is_valid_response(confirmed=False):
    def outer(func):
        @wraps(func)
        def inner(self, *args, **kwargs):
            donation, form = self.random_donation_and_form
            fake_save = fudge.Fake().is_callable().returns(donation)
            setattr(form, "save", fake_save)
            v = self.get_post_view(confirmed=confirmed)
            response = v.form_is_valid(form)
            func(self, response)
        return inner
    return outer


class DonationFormViewPostWithConfirmTestCase(BaseDonationFormViewTestCase):
    view_name = "donations_form_confirm"

    def test_use_confirm_template_false_by_default(self):
        v = views.DonationFormView()
        self.assertFalse(v.use_confirm_template)

    def test_use_confirm_template_true_if_confirmation_required(self):
        v = self.post_view
        self.assertTrue(v.use_confirm_template)

    def test_use_confirm_template_false_if_confirmed(self):
        v = self.get_post_view(confirmed=True)
        self.assertFalse(v.use_confirm_template)

    def test_use_confirm_template_false_if_confirmation_failed(self):
        v = self.post_view
        v.form_validation_failed = True
        self.assertFalse(v.use_confirm_template)

    def test_swaps_templates_on_confirmation(self):
        v = self.post_view
        self.assertEqual(v.confirm_template_name, v.get_template_names()[0])

    def test_uses_regular_template_when_confirmation_not_required(self):
        v = self.get_post_view(confirmed=True)
        self.assertEqual(v.template_name, v.get_template_names()[0])

    def test_uses_regular_template_on_get_request(self):
        v = views.DonationFormView(confirm=True)
        v.request = self.fake_get_request
        self.assertEqual(v.template_name, v.get_template_names()[0])

    def test_uses_regular_template_on_invalid_request(self):
        v = self.post_view
        v.form_validation_failed = True
        self.assertEqual(v.template_name, v.get_template_names()[0])

    def test_form_is_invalid_uses_regular_template(self):
        v = self.post_view
        response = v.form_is_invalid()
        self.assertEqual(v.template_name, response.template_name[0])

    def test_requires_confirmation_is_true_by_default_on_posts(self):
        self.assertTrue(self.post_view.requires_confirmation)

    def test_requires_confirmation_is_false_if_confirmed(self):
        v = self.get_post_view(confirmed=True)
        self.assertFalse(v.requires_confirmation)

    @form_is_valid_response()
    def test_form_is_valid_re_renders_if_confirmation_is_required(self, r):
        self.assertIsA(r, TemplateResponse)

    @form_is_valid_response()
    def test_contains_confirmation_required_in_context(self, r):
        self.assert_value_in_context(r, "confirmation_required", True)

    @form_is_valid_response(confirmed=True)
    def test_redirects_on_confirmed(self, r):
        self.assertIsA(r, HttpResponseRedirect)

    def test_form_is_invalid_receives_kwargs_from_post(self):
        r = lambda: random.randint(100, 200)
        random_kwargs = {
            "slug%d" % r(): "foo-%d" % r(),
        }

        donation_form = fudge.Fake()
        donation_form.provides("is_valid").returns(False)
        get_donation_form = fudge.Fake()
        get_donation_form.is_callable().returns(donation_form)

        form_is_invalid = fudge.Fake()
        form_is_invalid.expects_call().with_args(**random_kwargs)

        view = self.post_view
        with fudge.patched_context(view, "get_donation_form",
                get_donation_form):
            with fudge.patched_context(view, "form_is_invalid",
                    form_is_invalid):
                view.post({}, **random_kwargs)

        fudge.verify()

    def test_post_passes_kwargs_to_form_is_valid(self):
        r = lambda: random.randint(100, 200)
        random_kwargs = {
            "slug%d" % r(): "foo-%d" % r(),
        }
        donation_form = fudge.Fake()
        donation_form.provides("is_valid").returns(True)
        get_donation_form = fudge.Fake()
        get_donation_form.is_callable().returns(donation_form)

        form_is_valid = fudge.Fake()
        form_is_valid.expects_call().with_args(donation_form=donation_form,
                **random_kwargs)
        view = self.post_view
        with fudge.patched_context(view, "get_donation_form",
                get_donation_form):
            with fudge.patched_context(view, "form_is_valid", form_is_valid):
                view.post({}, **random_kwargs)

        fudge.verify()


class DonationFormViewPostTestCase(BaseDonationFormViewTestCase):
    @property
    def random_post_data(self):
        data = self.get_base_random_data()
        address_kwargs = self.random_address_kwargs
        prefixed_address_kwargs = self.prefix_data(address_kwargs,
                prefix="billing")
        data.update(prefixed_address_kwargs)
        return data

    def test_requires_confirmation_is_false(self):
        self.assertFalse(self.get_view_object().requires_confirmation)

    def test_saves_donation_on_post_with_minimal_information(self):
        name_kwargs = self.random_donor_kwargs
        random_amount = self.random_amount
        data = self.get_base_random_data(amount=random_amount,
                **name_kwargs)
        data.update(self.get_data_as_formset())

        # sanity check
        self.assertRaises(models.Donor.DoesNotExist,
                models.Donor.objects.get, **name_kwargs)
        with override_settings(ARMSTRONG_DONATION_FORM="SimpleDonationForm"):
            self.client.post(self.url, data)
        donor = models.Donor.objects.get(**name_kwargs)
        self.assertEqual(str(donor), " ".join(name_kwargs.values()))
        donation = models.Donation.objects.get(donor=donor)
        self.assertEqual(donation.amount, random_amount)

    def test_uses_promo_code_if_available(self):
        promo_code = self.random_discount
        name_kwargs = self.random_donor_kwargs
        random_amount = self. random_amount
        data = self.get_base_random_data(amount=random_amount,
                promo_code=promo_code.code, **name_kwargs)
        data.update(self.prefix_data(self.random_address_kwargs,
                prefix="billing"))

        self.client.post(self.url, data)
        donor = models.Donor.objects.get(**name_kwargs)
        donation = models.Donation.objects.get(donor=donor)
        self.assertEqual(promo_code, donation.code)

        d = fudge.Fake().has_attr(amount=random_amount)
        self.assertAlmostEqual(promo_code.calculate(d),
                donation.amount, places=2)

    def test_saves_address_if_present(self):
        name_kwargs = self.random_donor_kwargs
        address_kwargs = self.random_address_kwargs
        data = self.get_base_random_data(**name_kwargs)
        data.update(self.prefix_data(address_kwargs, prefix="billing"))

        self.client.post(self.url, data)
        donor = models.Donor.objects.get(**name_kwargs)
        address = models.DonorAddress.objects.get(**address_kwargs)
        self.assertEqual(address, donor.address)
        self.assertEqual(address, donor.mailing_address)

    def test_saves_mailing_address_if_present(self):
        name_kwargs = self.random_donor_kwargs
        address_kwargs = self.random_address_kwargs
        mailing_address_kwargs = self.random_address_kwargs
        data = self.get_base_random_data(**name_kwargs)
        data.update(self.prefix_data(address_kwargs, prefix="billing"))
        data.update(self.prefix_data(mailing_address_kwargs, prefix="mailing"))
        del data[constants.MAILING_SAME_AS_BILLING]

        self.assertEqual(0, len(models.DonorAddress.objects.all()),
            msg="sanity check")
        self.client.post(self.url, data)
        self.assertEqual(2, len(models.DonorAddress.objects.all()))
        address = models.DonorAddress.objects.get(**address_kwargs)
        mailing_address = models.DonorAddress.objects.get(
                **mailing_address_kwargs)
        self.assertNotEqual(address, mailing_address)

        donor = models.Donor.objects.get(**name_kwargs)
        self.assertEqual(address, donor.address)
        self.assertEqual(mailing_address, donor.mailing_address)

    def test_only_saves_donor_once(self):
        """
        Verify the number of queries that are run.

        This assumes that the tests are run in isolation from the backend.

        This will pass if #17594 is merged in.
        """
        data = self.random_post_data
        with self.assertNumQueries(3):
            self.client.post(self.url, data)

    def test_saves_mailing_address_if_same_as_billing_is_checked(self):
        data = self.random_post_data
        data["mailing_same_as_billing"] = u"1"
        self.client.post(self.url, data)
        donor = models.Donor.objects.get(first_name=data["first_name"],
                last_name=data["last_name"])
        self.assertEqual(donor.address, donor.mailing_address)

    def test_same_as_billing_overrides_second_address(self):
        data = self.random_post_data
        data.update(self.prefix_data(self.random_address_kwargs,
                prefix="billing"))
        data.update(self.prefix_data(self.random_address_kwargs,
                prefix="mailing"))
        data["mailing_same_as_billing"] = u"1"
        self.client.post(self.url, data)
        donor = models.Donor.objects.get(first_name=data["first_name"],
                last_name=data["last_name"])
        self.assertEqual(donor.address, donor.mailing_address)

    def test_redirects_to_success_url_after_successful_save(self):
        data = self.random_post_data
        response = self.client.post(self.url, data)
        self.assertRedirects(response, reverse("donations_thanks"))

    def test_displays_error_on_donation_form_validation_error(self):
        data = self.random_post_data
        del data["ccv_code"]
        response = self.client.post(self.url, data)
        self.assert_template("armstrong/donations/donation.html", response)
        self.assert_form_has_errors(response, "donation_form", ["ccv_code", ])

    def test_displays_errors_on_address_validation_error(self):
        data = self.random_post_data
        data["billing-address"] = ""
        response = self.client.post(self.url, data)
        self.assert_template("armstrong/donations/donation.html", response)
        self.assert_subform_has_errors(response, "billing_address_form")

    def test_displays_errors_on_mailing_address_validation_error(self):
        data = self.random_post_data
        data.update(self.prefix_data(self.random_address_kwargs,
                prefix="billing"))
        data.update(self.prefix_data(self.random_address_kwargs,
                prefix="mailing"))
        del data["mailing_same_as_billing"]
        data["mailing-address"] = ""
        response = self.client.post(self.url, data)

        self.assert_template("armstrong/donations/donation.html", response)
        self.assert_subform_has_errors(response, "mailing_address_form")

    @failed_purchase
    def test_does_redisplays_form_on_failed_donation(self, response, **kwargs):
        self.assertEqual(200, response.status_code)
        self.assert_template("armstrong/donations/donation.html", response)

    @failed_purchase
    def test_error_msg_in_context_on_failed_purchase(self, response, **kwargs):
        self.assert_value_in_context(response, "error_msg",
                "Unable to process payment")

    @failed_purchase
    def test_reason_in_context_on_failed_purchase(self, response, random_text,
            **kwargs):
        self.assert_value_in_context(response, "reason", random_text)

    @failed_purchase
    def test_response_in_context_on_failed_purchase(self, response,
            backend_response, **kwargs):
        self.assert_value_in_context(response, "response", backend_response)
