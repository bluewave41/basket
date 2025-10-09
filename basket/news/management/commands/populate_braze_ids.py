from django.core.management.base import BaseCommand

from basket.news.models import Newsletter


class Command(BaseCommand):
    help = "Populate braze_id for all newsletters"

    def handle(self, *args, **kwargs):
        braze_mapping = {
            "mozilla-and-you": "96f6577e-6efd-4744-9d96-dbe67b1f48c5",
            "mozilla-foundation": "c7349bcb-0aae-43d6-a8ef-fc8d5cf68a99",
        }
        for newsletter in Newsletter.objects.all():
            newsletter.braze_id = braze_mapping.get(newsletter.slug, None)
            newsletter.save(update_fields=["braze_id"])
