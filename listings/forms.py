from django import forms
from django.urls import reverse

from .models import AMENITIES, HOUSE_TYPES, ORIENTATIONS, PAYMENT_CHOICES, Listing, Region


class AmenityCheckboxSelect(forms.CheckboxSelectMultiple):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        option['attrs']['class'] = 'peer sr-only'
        return option


class ListingForm(forms.ModelForm):
    amenities = forms.MultipleChoiceField(
        label='设施',
        choices=[(item, item) for item in AMENITIES],
        widget=AmenityCheckboxSelect,
        required=False,
    )

    class Meta:
        model = Listing
        fields = [
            'title',
            'province',
            'city',
            'district',
            'address',
            'house_type',
            'area',
            'floor',
            'orientation',
            'rent',
            'payment',
            'amenities',
            'description',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'input input-bordered w-full field-glow', 'placeholder': '例如：云栖小筑 · 徐汇一室'}),
            'province': forms.Select(),
            'city': forms.Select(),
            'district': forms.Select(),
            'address': forms.TextInput(attrs={'class': 'input input-bordered w-full field-glow', 'placeholder': '详细地址，仅签约后向租客展示完整门牌'}),
            'house_type': forms.Select(attrs={'class': 'select select-bordered w-full field-glow'}),
            'area': forms.NumberInput(attrs={'class': 'input input-bordered w-full field-glow', 'min': 5, 'max': 500}),
            'floor': forms.TextInput(attrs={'class': 'input input-bordered w-full field-glow', 'placeholder': '例如 5/18 层'}),
            'orientation': forms.Select(attrs={'class': 'select select-bordered w-full field-glow'}),
            'rent': forms.NumberInput(attrs={'class': 'input input-bordered w-full field-glow', 'min': 500, 'max': 50000, 'step': 100}),
            'payment': forms.Select(attrs={'class': 'select select-bordered w-full field-glow'}),
            'description': forms.Textarea(attrs={'class': 'textarea textarea-bordered w-full field-glow min-h-32', 'rows': 4, 'placeholder': '介绍一下采光、通勤、周边生活，至少 20 字'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        endpoint = reverse('listings:region_options')
        select_class = 'select select-bordered w-full field-glow'
        instance = self.instance

        province_code = self.data.get('province') or (
            instance.province.code if instance and instance.pk and instance.province_id else ''
        )
        city_code = self.data.get('city') or (
            instance.city.code if instance and instance.pk and instance.city_id else ''
        )

        for name in ('province', 'city', 'district'):
            self.fields[name].to_field_name = 'code'
        if instance and instance.pk:
            # to_field_name=code 时 option value 是区划 code，而 model_to_dict 给的是 pk
            self.initial['province'] = instance.province.code
            self.initial['city'] = instance.city.code
            self.initial['district'] = instance.district.code

        self.fields['province'].queryset = Region.objects.filter(level=Region.LEVEL_PROVINCE).order_by('code')
        if province_code:
            self.fields['city'].queryset = Region.objects.filter(
                level=Region.LEVEL_CITY, parent__code=province_code
            ).order_by('code')
        else:
            self.fields['city'].queryset = Region.objects.filter(level=Region.LEVEL_CITY).order_by('code')
        if city_code:
            self.fields['district'].queryset = Region.objects.filter(
                level=Region.LEVEL_DISTRICT, parent__code=city_code
            ).order_by('code')
        else:
            self.fields['district'].queryset = Region.objects.none()

        self.fields['province'].widget.attrs.update(
            {
                'class': select_class,
                'hx-get': f'{endpoint}?level={Region.LEVEL_CITY}',
                'hx-trigger': 'change',
                'hx-target': '#id_city',
                'hx-include': 'this',
                'hx-swap': 'innerHTML',
            }
        )
        self.fields['city'].widget.attrs.update(
            {
                'class': select_class,
                'hx-get': f'{endpoint}?level={Region.LEVEL_DISTRICT}',
                'hx-trigger': 'change',
                'hx-target': '#id_district',
                'hx-include': 'this',
                'hx-swap': 'innerHTML',
            }
        )
        self.fields['district'].widget.attrs.update({'class': select_class})

    def clean(self):
        cleaned = super().clean()
        province = cleaned.get('province')
        city = cleaned.get('city')
        district = cleaned.get('district')

        if city and province and city.parent_id != province.pk:
            self.add_error('city', '所选城市不属于该省份，请重新选择')
        if district and city and district.parent_id != city.pk:
            self.add_error('district', '所选区县不属于该城市，请重新选择')
        return cleaned

    def clean_area(self):
        area = self.cleaned_data['area']
        if area < 5 or area > 500:
            raise forms.ValidationError('面积需在 5–500 ㎡ 之间')
        return area

    def clean_rent(self):
        rent = self.cleaned_data['rent']
        if rent < 500 or rent > 50000:
            raise forms.ValidationError('月租金需在 500–50000 元之间')
        return rent

    def clean_description(self):
        description = self.cleaned_data['description'].strip()
        if len(description) < 20:
            raise forms.ValidationError('房源描述至少 20 字，方便租客了解房子')
        return description

    def clean_amenities(self):
        return list(self.cleaned_data.get('amenities') or [])

    def clean_floor(self):
        floor = self.cleaned_data['floor'].strip()
        if not floor:
            raise forms.ValidationError('请填写楼层')
        return floor


ORIENTATION_CHOICES = ORIENTATIONS
PAYMENT_CHOICES_UI = PAYMENT_CHOICES
