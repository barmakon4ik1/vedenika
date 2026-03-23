from rest_framework import serializers
from .models import *

class CatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cat
        fields = '__all__'

class ContentBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentBlock
        fields = ['block_type', 'title', 'text', 'image', 'order']

class PageSerializer(serializers.ModelSerializer):
    blocks = ContentBlockSerializer(many=True, read_only=True)

    class Meta:
        model = Page
        fields = ['slug', 'name', 'blocks']
