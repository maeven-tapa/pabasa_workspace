from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0036_principal_security')]
    operations = [
        migrations.AddField(model_name='storyresponsesubmission', name='reviewed_at',
            field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='storyresponsesubmission', name='reviewed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='reviewed_story_responses', to='pabasa_app.user')),
        migrations.CreateModel(name='TeacherReviewInbox', fields=[
            ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('seen_tokens', models.JSONField(default=list)),
            ('notification', models.ForeignKey(blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL, to='pabasa_app.notification')),
            ('teacher', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                related_name='review_inbox', to='pabasa_app.user')),
        ]),
    ]
