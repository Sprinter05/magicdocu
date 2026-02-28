import django_elasticsearch_dsl as elastic_dsl
from django_elasticsearch_dsl.registries import registry
from .models import Document

@registry.register_document
class ElasticDoc(elastic_dsl.Document):
    class Index:
        name = 'document'
    
    class Django:    
        model = Document
    fields = [
        'file',
        'author',
        'filetype',
        'modified_date',
        'created_date',
        'accessed_date',
        'size',
        'summary',       
    ]