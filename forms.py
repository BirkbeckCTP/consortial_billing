from django import forms
from django.utils import timezone

from plugins.consortial_billing import models as supporter_models, logic


class BaseBandForm(forms.ModelForm):

    class Meta:
        model = supporter_models.Band
        fields = [
            'country',
            'currency',
            'size',
            'level',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['country'].required = True
        self.fields['currency'].required = True
        self.fields['size'].required = True
        self.fields['level'].required = True

    def save(self, commit=True):
        """
        Populates a band object matching the form input.
        If there is already a matching object, it is returned
        rather than a new one to prevent duplicate bands from proliferating.
        """

        band = super().save(commit=False)
        band.billing_agent = logic.determine_billing_agent(band.country)

        if band.category == 'calculated':
            # For calculated bands, we try to avoid duplicates to make management easier
            band.fee, band.warnings = band.calculate_fee()
            matches = supporter_models.Band.objects.filter(
                level=band.level,
                size=band.size,
                country=band.country,
                currency=band.currency,
                billing_agent=band.billing_agent,
                category=band.category,
                fee=band.fee,
                warnings=band.warnings,
                datetime__year=timezone.now().year,
            )
            if matches:
                band = matches.latest()

        if commit:
            band.save()
        return band


class BandForm(BaseBandForm):

    class Meta(BaseBandForm.Meta):
        fields = [
            'country',
            'currency',
            'size',
            'level',
            'fee',
            'category',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fee'].required = False
        self.fields['fee'].disabled = True


class EditBandForm(BaseBandForm):

    class Meta(BaseBandForm.Meta):
        fields = [
            'level',
            'size',
            'country',
            'currency',
            'fee',
            'category',
            'billing_agent',
            'warnings',
        ]
        help_texts = {
            'billing_agent': 'To change the billing agent, select the appropriate country and currency.',
            'fee': 'To edit this field, set the band category to special. To auto-calculate it, set the band category to calculated.',
            'category': 'Whether the fee is calculated or special for this supporter',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['billing_agent'].disabled = True
        self.fields['warnings'].disabled = True
        self.fields['fee'].required = True
        all_category_choices = supporter_models.BAND_CATEGORY_CHOICES
        choices_without_base = [c for c in all_category_choices if c[0] != 'base']
        self.fields['category'].widget.choices = choices_without_base
        if self.instance:
            if self.instance.category == 'special':
                self.fields['fee'].disabled = False
            elif self.instance.category == 'calculated':
                self.fields['fee'].disabled = True
                self.fields['fee'].required = False


class SupporterSignupForm(forms.ModelForm):

    class Meta:
        model = supporter_models.Supporter
        fields = [
            'name',
            'ror',
            'address',
            'postal_code',
            'display',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = True


class EditSupporterForm(SupporterSignupForm):

    class Meta(SupporterSignupForm.Meta):
        fields = [
            'name',
            'ror',
            'address',
            'postal_code',
            'display',
            'active',
            'internal_notes',
        ]


class AccountAdminSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={'type': 'search'}
        ),
        label='Search existing accounts to add a new contact',
    )
