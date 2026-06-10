from django import forms        # Import Django form tools
from .models import GameServer  # Imports our GameServer model from models.py

# Creating form class. ModelForm = build this form from a Django model
class GameServerNotesForm(forms.ModelForm):
    # Meta class is how Django knows which model this form is connected to
    class Meta:
        model = GameServer  # This form edits GameServer objects
        fields = "__all__"  # Form shows all fields or optionally can set to ["desired", "fields"]

