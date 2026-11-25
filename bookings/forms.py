from datetime import date

from django import forms

from .models import Viewing


class ViewingForm(forms.ModelForm):
    class Meta:
        model = Viewing
        fields = ['name', 'phone', 'visit_date', 'note']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input input-bordered w-full field-glow', 'placeholder': '怎么称呼您'}),
            'phone': forms.TextInput(
                attrs={
                    'class': 'input input-bordered w-full field-glow',
                    'placeholder': '1 开头的 11 位手机号',
                    'inputmode': 'numeric',
                    'maxlength': 11,
                }
            ),
            'visit_date': forms.DateInput(
                attrs={'class': 'input input-bordered w-full field-glow', 'type': 'date'},
                format='%Y-%m-%d',
            ),
            'note': forms.TextInput(attrs={'class': 'input input-bordered w-full field-glow', 'placeholder': '选填，比如方便的时间段'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['visit_date'].input_formats = ['%Y-%m-%d']
        self.fields['visit_date'].widget.attrs['min'] = date.today().isoformat()

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        if len(phone) != 11 or not phone.isdigit() or not phone.startswith('1'):
            raise forms.ValidationError('请输入 1 开头的 11 位手机号')
        return phone

    def clean_visit_date(self):
        visit_date = self.cleaned_data['visit_date']
        if visit_date < date.today():
            raise forms.ValidationError('看房日期不能早于今天')
        return visit_date
