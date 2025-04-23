import datetime
import uuid

import factory
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from factory import Faker
from factory import LazyAttribute
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice
from factory.fuzzy import FuzzyInteger

from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import MatchingModel
from documents.models import Note
from documents.models import PaperlessTask
from documents.models import SavedView
from documents.models import SavedViewFilterRule
from documents.models import ShareLink
from documents.models import StoragePath
from documents.models import Tag
from documents.models import UiSettings
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowActionEmail
from documents.models import WorkflowActionWebhook
from documents.models import WorkflowRun
from documents.models import WorkflowTrigger

User = get_user_model()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: f"user_{n}")  # Simple unique username
    email = Faker("email")
    first_name = Faker("first_name")
    last_name = Faker("last_name")
    is_staff = False
    is_superuser = False
    is_active = True  # True so it can be used by default
    password = factory.django.Password("password")


class MatchingModelFactoryMixin(factory.Factory):
    name = factory.Sequence(lambda n: f"match_item_{n}")
    match = Faker("word")
    matching_algorithm = FuzzyChoice(
        [
            MatchingModel.MATCH_ANY,
            MatchingModel.MATCH_ALL,
            MatchingModel.MATCH_LITERAL,
            MatchingModel.MATCH_REGEX,
            MatchingModel.MATCH_FUZZY,
        ],
    )
    is_insensitive = Faker("boolean")
    owner = factory.SubFactory(UserFactory, is_active=True)


class CorrespondentFactory(MatchingModelFactoryMixin, DjangoModelFactory):
    class Meta:
        model = Correspondent
        django_get_or_create = ("name", "owner")


class TagFactory(MatchingModelFactoryMixin, DjangoModelFactory):
    class Meta:
        model = Tag
        django_get_or_create = ("name", "owner")

    color = Faker("hex_color")
    is_inbox_tag = False


class DocumentTypeFactory(MatchingModelFactoryMixin, DjangoModelFactory):
    class Meta:
        model = DocumentType
        django_get_or_create = ("name", "owner")


class StoragePathFactory(MatchingModelFactoryMixin, DjangoModelFactory):
    class Meta:
        model = StoragePath
        django_get_or_create = ("name", "owner")

    path = factory.Sequence(lambda n: f"/path/to/storage/{n}")


class DocumentFactory(DjangoModelFactory):
    class Meta:
        model = Document
        skip_postgeneration_save = True

    correspondent = None
    title = factory.Sequence(lambda n: f"Document {n}")
    content = Faker("paragraph", nb_sentences=5)
    mime_type = FuzzyChoice(
        ["application/pdf", "image/png", "image/jpeg", "text/plain"],
    )
    checksum = factory.Sequence(lambda n: f"{uuid.uuid4().hex}")
    archive_checksum = factory.Sequence(lambda n: f"{uuid.uuid4().hex}")
    created = factory.LazyFunction(timezone.now)
    modified = factory.LazyFunction(timezone.now)
    added = factory.LazyFunction(timezone.now)
    storage_type = Document.STORAGE_TYPE_UNENCRYPTED
    filename = factory.LazyAttribute(lambda o: f"filename_{id(o)}.pdf")
    archive_filename = factory.LazyAttribute(lambda o: f"archive_filename_{id(o)}.pdf")
    original_filename = factory.Sequence(lambda n: f"original_{n}.pdf")
    page_count = FuzzyInteger(1, 100)

    @factory.post_generation
    def set_final_filenames(obj: Document, create, extract, **kwargs):
        """
        To run once the object is created, an update the file name
        """
        if not create:
            return
        obj.filename = str(settings.ORIGINALS_DIR / f"{obj.pk:07}.pdf")
        obj.archive_filename = str(settings.ARCHIVE_DIR / f"{obj.pk:07}.pdf")
        obj.save()


class SavedViewFactory(DjangoModelFactory):
    class Meta:
        model = SavedView

    owner = None
    name = Faker("word")
    show_on_dashboard = Faker("boolean")
    show_in_sidebar = Faker("boolean")
    sort_field = "created"
    sort_reverse = False


class SavedViewFilterRuleFactory(DjangoModelFactory):
    class Meta:
        model = SavedViewFilterRule

    saved_view = factory.SubFactory(SavedViewFactory)
    rule_type = factory.fuzzy.FuzzyChoice(
        [item[0] for item in SavedViewFilterRule.RULE_TYPES],
    )
    value = Faker("word")


class UiSettingsFactory(DjangoModelFactory):
    class Meta:
        model = UiSettings

    user = factory.SubFactory(UserFactory)
    settings = factory.LazyFunction(lambda: {"theme": "dark"})


class PaperlessTaskFactory(DjangoModelFactory):
    class Meta:
        model = PaperlessTask

    owner = None
    task_id = Faker("uuid4")
    task_file_name = Faker("file_name", extension="pdf")
    status = factory.fuzzy.FuzzyChoice(PaperlessTask.ALL_STATES)
    date_created = factory.LazyFunction(timezone.now)


class NoteFactory(DjangoModelFactory):
    class Meta:
        model = Note

    note = Faker("paragraph")
    created = factory.LazyFunction(timezone.now)
    document = factory.SubFactory(DocumentFactory)
    user = factory.SubFactory(UserFactory)


class ShareLinkFactory(DjangoModelFactory):
    class Meta:
        model = ShareLink

    created = factory.LazyFunction(timezone.now)
    expiration = factory.LazyAttribute(lambda o: o.created + datetime.timedelta(days=7))
    slug = factory.Sequence(lambda n: f"share-link-{n}")
    document = factory.SubFactory(DocumentFactory)
    file_version = ShareLink.FileVersion.ARCHIVE
    owner = factory.SubFactory(UserFactory)


class CustomFieldFactory(DjangoModelFactory):
    class Meta:
        model = CustomField

    name = factory.Sequence(lambda n: f"custom_field_{n}")
    data_type = CustomField.FieldDataType.STRING


class CustomFieldInstanceFactory(DjangoModelFactory):
    class Meta:
        model = CustomFieldInstance

    created = factory.LazyFunction(timezone.now)
    document = factory.SubFactory(DocumentFactory)
    field = factory.SubFactory(CustomFieldFactory)

    @LazyAttribute
    def _set_value(self):
        data_type = self.field.data_type
        faker = Faker()
        value = None
        if data_type == CustomField.FieldDataType.STRING:
            value = faker.word()
            self.value_text = value
        elif data_type == CustomField.FieldDataType.URL:
            value = faker.url()
            self.value_url = value
        elif data_type == CustomField.FieldDataType.DATE:
            value = faker.date_object()
            self.value_date = value
        elif data_type == CustomField.FieldDataType.BOOL:
            value = faker.boolean()
            self.value_bool = value
        elif data_type == CustomField.FieldDataType.INT:
            value = faker.random_int()
            self.value_int = value
        elif data_type == CustomField.FieldDataType.FLOAT:
            value = faker.pyfloat()
            self.value_float = value
        elif data_type == CustomField.FieldDataType.MONETARY:
            value = f"{faker.currency_symbol()}{faker.pyfloat(left_digits=3, right_digits=2)}"
            self.value_monetary = value
        elif data_type == CustomField.FieldDataType.DOCUMENTLINK:
            # For DocumentLink, you'll likely need to create or select existing Document IDs
            # This example creates a list of 1-3 random IDs. Adjust as needed.
            value = [
                DocumentFactory().id for _ in range(faker.random_int(min=1, max=3))
            ]
            self.value_document_ids = value
        elif data_type == CustomField.FieldDataType.SELECT:
            # If your CustomField model has a `options` field (e.g., a JSON list),
            # you would ideally select from those. For now, let's just use a word.
            value = faker.word()
            self.value_select = value
        return value


class WorkflowTriggerFactory(DjangoModelFactory):
    class Meta:
        model = WorkflowTrigger

    type = WorkflowTrigger.WorkflowTriggerType.CONSUMPTION
    filter_filename = factory.LazyAttribute(
        lambda o: f"*{Faker('word').generate()}.pdf",
    )
    matching_algorithm = WorkflowTrigger.WorkflowTriggerMatching.NONE


class WorkflowActionEmailFactory(DjangoModelFactory):
    class Meta:
        model = WorkflowActionEmail

    subject = Faker("sentence")
    body = Faker("paragraph")
    to = Faker("email")
    include_document = False


class WorkflowActionWebhookFactory(DjangoModelFactory):
    class Meta:
        model = WorkflowActionWebhook

    url = Faker("url")
    use_params = True
    as_json = False
    params = factory.LazyFunction(lambda: {"param1": "value1"})


class WorkflowActionFactory(DjangoModelFactory):
    class Meta:
        model = WorkflowAction

    type = WorkflowAction.WorkflowActionType.ASSIGNMENT
    assign_title = Faker("sentence")

    @factory.post_generation
    def assign_tags(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for tag in extracted:
                self.assign_tags.add(tag)


class WorkflowFactory(DjangoModelFactory):
    class Meta:
        model = Workflow

    name = factory.Sequence(lambda n: f"workflow_{n}")
    order = factory.Sequence(lambda n: n)
    enabled = True

    @factory.post_generation
    def triggers(self, create, extracted, **kwargs):
        if not create:
            return

        if not extracted:
            # Create at least one trigger by default
            trigger = WorkflowTriggerFactory()
            self.triggers.add(trigger)
        else:
            for trigger in extracted:
                self.triggers.add(trigger)

    @factory.post_generation
    def actions(self, create, extracted, **kwargs):
        if not create:
            return

        if not extracted:
            # Create at least one action by default
            action = WorkflowActionFactory()
            self.actions.add(action)
        else:
            for action in extracted:
                self.actions.add(action)


class WorkflowRunFactory(DjangoModelFactory):
    class Meta:
        model = WorkflowRun

    workflow = factory.SubFactory(WorkflowFactory)
    type = WorkflowTrigger.WorkflowTriggerType.CONSUMPTION
    document = factory.SubFactory(DocumentFactory)
    run_at = factory.LazyFunction(timezone.now)
