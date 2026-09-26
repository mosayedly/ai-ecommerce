"""ModelForms for the custom admin dashboard (Phase 2: products & categories).

Every widget carries a shared CSS class (``form-input``, ``form-select``,
``form-textarea``, ``form-file``, ``form-checkbox``) so the dashboard forms use
one consistent visual language, styled by the dashboard section of
``static/css/styles.css``.
"""

from django import forms

from .models import Category, Product, unique_slugify

_FORM_INPUT = "form-input"
_FORM_SELECT = "form-select"
_FORM_TEXTAREA = "form-textarea"
_FORM_FILE = "form-file"
_FORM_CHECKBOX = "form-checkbox"


class ProductAdminForm(forms.ModelForm):
    """Create or update a product from the dashboard."""

    # Declared explicitly so the negative-value guards below own the validation
    # (and therefore the error messages) instead of the model validators.
    price = forms.DecimalField(
        label="Price",
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={"class": _FORM_INPUT, "step": "0.01", "min": "0", "placeholder": "0.00"}
        ),
        help_text="Unit price in USD (0 or more).",
    )
    stock = forms.IntegerField(
        label="Stock",
        widget=forms.NumberInput(attrs={"class": _FORM_INPUT, "min": "0", "placeholder": "0"}),
        help_text="Units available in inventory (0 or more).",
    )

    class Meta:
        model = Product
        fields = [
            "name",
            "slug",
            "category",
            "description",
            "price",
            "stock",
            "image",
            "status",
            "is_featured",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": _FORM_INPUT, "placeholder": "e.g. Wireless Mouse"}
            ),
            "slug": forms.TextInput(
                attrs={
                    "class": _FORM_INPUT,
                    "placeholder": "auto-generated from the name when left blank",
                }
            ),
            "category": forms.Select(attrs={"class": _FORM_SELECT}),
            "description": forms.Textarea(attrs={"class": _FORM_TEXTAREA, "rows": 5}),
            "image": forms.ClearableFileInput(attrs={"class": _FORM_FILE}),
            "status": forms.Select(attrs={"class": _FORM_SELECT}),
            "is_featured": forms.CheckboxInput(attrs={"class": _FORM_CHECKBOX}),
        }
        help_texts = {
            "slug": "Leave blank to auto-generate a unique slug from the name.",
            "category": "Optional — products without a category are uncategorized.",
            "description": "Shown on the product detail page.",
            "image": "Optional product photo (JPG or PNG).",
            "status": "Only active products are visible to customers.",
            "is_featured": "Featured products are highlighted on the storefront home page.",
        }

    def clean_price(self):
        price = self.cleaned_data.get("price")
        if price is not None and price < 0:
            raise forms.ValidationError("Price cannot be negative.")
        return price

    def clean_stock(self):
        stock = self.cleaned_data.get("stock")
        if stock is not None and stock < 0:
            raise forms.ValidationError("Stock cannot be negative.")
        return stock

    def clean_slug(self):
        """Return the slug, generating a unique one from the name when blank."""
        slug = (self.cleaned_data.get("slug") or "").strip()
        if slug:
            return slug
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            return ""
        return unique_slugify(self.instance, name)


class CategoryAdminForm(forms.ModelForm):
    """Create or update a category from the dashboard."""

    class Meta:
        model = Category
        fields = ["name", "slug", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": _FORM_INPUT, "placeholder": "e.g. Electronics"}
            ),
            "slug": forms.TextInput(
                attrs={
                    "class": _FORM_INPUT,
                    "placeholder": "auto-generated from the name when left blank",
                }
            ),
            "description": forms.Textarea(attrs={"class": _FORM_TEXTAREA, "rows": 4}),
        }
        help_texts = {
            "slug": "Leave blank to auto-generate a unique slug from the name.",
            "description": "Optional summary of what belongs in this category.",
        }

    def clean_slug(self):
        """Return the slug, generating a unique one from the name when blank."""
        slug = (self.cleaned_data.get("slug") or "").strip()
        if slug:
            return slug
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            return ""
        return unique_slugify(self.instance, name)
