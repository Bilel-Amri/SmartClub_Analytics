from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat_llm', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatsession',
            name='conv_state',
            field=models.CharField(blank=True, default='', max_length=30),
        ),
        migrations.AddField(
            model_name='chatsession',
            name='conv_data',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
