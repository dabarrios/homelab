from django import forms        # Import Django form tools
from .models import GameServer  # Imports our GameServer model from models.py

# Creating form class. ModelForm = build this form from a Django model
class GameServerGameNameForm(forms.ModelForm):
    # Meta class is how Django knows which model this form is connected to
    class Meta:
        model = GameServer  # This form edits GameServer objects
        fields = ["game"]  # Form shows all fields or optionally can set to ["desired", "fields"]

class GameServerWorldNameForm(forms.ModelForm):
    class Meta:
        model = GameServer
        fields = ["world_name"]
        
class GameServerSlugForm(forms.ModelForm):
    class Meta:
        model = GameServer
        fields = ["slug"]
        
class GameServerContainerNameForm(forms.ModelForm):
    class Meta:
        model = GameServer
        fields = ["container_name"]
        
class GameServerAllocatedMemoryForm(forms.ModelForm):
    class Meta:
        model = GameServer
        fields = ["allocated_memory"]
        
class GameServerVersionForm(forms.ModelForm):
    class Meta:
        model = GameServer
        fields = ["version"]
        
class GameServerPortForm(forms.ModelForm):
    class Meta:
        model = GameServer
        fields = ["port"]
        
class GameServerIsActiveForm(forms.ModelForm):
    class Meta:
        model = GameServer
        fields = ["is_active"]
        
class GameServerNotesForm(forms.ModelForm):
    class Meta:
        model = GameServer
        fields = ["notes"]