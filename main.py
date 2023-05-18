import settings
import discord
import typing
from discord.ext import commands
from datetime import datetime
from firestore_db import db
from discord import app_commands
from firebase_admin import firestore
import json

import asyncio
import async_google_trans_new

logger = settings.logging.getLogger("bot")

class EventsGroup(app_commands.Group):
    @app_commands.command(name="post", description="Post an event to The UMB CS Club Website")
    async def post(self, interaction: discord.Interaction):
        event_creation_modal = EventCreationModal(title="Create test")
        await interaction.response.send_modal(event_creation_modal)

    @app_commands.command(name="get", description="Get all events on The UMB CS Club Website")
    async def get(self, interaction: discord.Interaction, id: str | None = None, lang: str = "en"):
        if not db.collection("events").document(id).get().exists and id:
            await interaction.response.send_message("That event ID does not exist")
            return
        elif not lang in db.collection("site").document("language_support").get().to_dict()['languages']:
            await interaction.response.send_message("That language is not supported")
            return

        events = db.collection("events").stream()
        embed = discord.Embed(
            title="Events",
            color=discord.Color.blue()
        )
        for event in events:
            if id and event.id != id:
                continue
            
            embed.add_field(name="Event ID", value=event.id, inline=False)
            embed.add_field(name="Start", value=str(event.get("start")), inline=True)
            embed.add_field(name="End", value=str(event.get("end")), inline=True)
            embed.add_field(name=event.get("title")[lang], value=event.get('desc')[lang], inline=False)
        await interaction.response.send_message(embed=embed)

    @get.autocomplete("id")
    async def get_autocompletion_id(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> typing.List[app_commands.Choice[str]]:
        data = []
        for event in db.collection("events").stream():
            if current.lower() in event.id.lower():
                data.append(app_commands.Choice(name=event.id, value=event.id))
        return data
    
    @get.autocomplete("lang")
    async def get_autocompletion_lang(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> typing.List[app_commands.Choice[str]]:
        data = []
        doc_ref = db.collection('site').document('language_support')
        supported_languages = doc_ref.get().to_dict()['languages']
        for lang in supported_languages:
            if current.lower() in lang.lower():
                data.append(app_commands.Choice(name=lang, value=lang))
        return data


    @app_commands.command(name="delete", description="Delete an event from The UMB CS Club Website")
    async def delete(self, interaction: discord.Interaction, id: str):
        if not id:
            await interaction.response.send_message("Please provide an event ID to delete")
            return
        elif not db.collection("events").document(id).get().exists:
            await interaction.response.send_message("That event ID does not exist")
            return

        class EventDeletionView(discord.ui.View):
            @discord.ui.button(label="Confirm Event Deletion ✅", style=discord.ButtonStyle.success)
            async def confirm_event_deletion(self, interaction: discord.Interaction, button: discord.ui.Button):
                db.collection("events").document(id).delete()
                await interaction.response.edit_message(view=None)
                await interaction.followup.send("Event deleted successfully!")
                self.stop()

            @discord.ui.button(label="Cancel Event Deletion ❌", style=discord.ButtonStyle.danger)
            async def cancel_event_deletion(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.edit_message(view=None)
                await interaction.followup.send("Event deletion cancelled!")
                self.stop()

        view = EventDeletionView()
        await interaction.response.send_message("Are you sure you want to delete this event?", view=view)
        await view.wait()

    @delete.autocomplete("id")
    async def delete_autocompletion_id(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> typing.List[app_commands.Choice[str]]:
        data = []
        for event in db.collection("events").stream():
            if current.lower() in event.id.lower():
                data.append(app_commands.Choice(name=event.id, value=event.id))
        return data

    @app_commands.command(name="put", description="Update an event on The UMB CS Club Website")
    async def put(self, interaction: discord.Interaction, id: str):
        if not id:
            await interaction.response.send_message("Please provide an event ID to update")
            return
        elif not db.collection("events").document(id).get().exists:
            await interaction.response.send_message("That event ID does not exist")
            return
        
        existing_event = db.collection("events").document(id).get()
        

        class EventUpdateModal(discord.ui.Modal, title="Editing Event..."):
            event_title = discord.ui.TextInput(
                style=discord.TextStyle.short,
                label="Title", 
                placeholder="Give your event a title",
                default=existing_event.get("title")["en"],
                required=False
            )

            event_date = discord.ui.TextInput(
                style=discord.TextStyle.short,
                label="Date", 
                placeholder="MM/DD/YYYY",
                default=existing_event.get("start").strftime('%m/%d/%Y'),
                required=False
            )

            event_time = discord.ui.TextInput(
                style=discord.TextStyle.short,
                label="Start Time - End Time (24 Hour, EST Time)", 
                placeholder="HH:MM-HH:MM",
                default=f"{existing_event.get('start').strftime('%H:%M')}-{existing_event.get('end').strftime('%H:%M')}",
                required=False
            )

            event_place = discord.ui.TextInput(
                style=discord.TextStyle.short,
                label="Place",
                default=existing_event.get("where")["en"],
                placeholder="Where is the event taking place?",
                required=True
            )

            event_description = discord.ui.TextInput(
                style=discord.TextStyle.long,
                label="Description", 
                placeholder="Give your event a description",
                default=existing_event.get("desc")["en"],
                max_length=1000,
                required=False
            )

            async def on_submit(self, interaction: discord.Interaction):
                now = datetime.now()
                year = now.year
                month = now.month
                day = now.day
                hour = now.hour
                minute = now.minute

                embed = discord.Embed(
                    title=f"Event Updated @ {month}/{day}/{year} {hour}:{minute}EST",
                    color=discord.Color.yellow(),
                    
                )

                embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar)
                embed.add_field(name="Title", value=f"{existing_event.get('title')['en']} ➡️ {self.event_title.value}", inline=False)
                embed.add_field(name="Date", value=f"{existing_event.get('start').strftime('%m/%d/%Y')} ➡️ {self.event_date.value}", inline=False)
                embed.add_field(name="Time", value=f"{existing_event.get('start').strftime('%H:%M')}-{existing_event.get('end').strftime('%H:%M')} ➡️ {self.event_time.value}", inline=False)
                embed.add_field(name="Location", value=f"{existing_event.get('where')['en']} ➡️ {self.event_place.value}", inline=False)
                embed.add_field(name="Description", value=existing_event.get("desc")["en"], inline=False)
                embed.add_field(name="", value="⬇️", inline=False)
                embed.add_field(name="", value=self.event_description.value, inline=False)
                embed.set_footer(text="Status: pending")
                
                class EventChangesSubmissionView(discord.ui.View):
                    modal = self
                    @discord.ui.button(label="Confirm Event Changes ✅", style=discord.ButtonStyle.success)
                    async def confirm_event(self, interaction: discord.Interaction, button: discord.ui.Button):
                        languages = db.collection('site').document('language_support').get().to_dict()['languages']
                        translated_title = {}
                        translated_desc = {}
                        translated_place = {}
                        async def translate_all():
                            
                            g = async_google_trans_new.AsyncTranslator()
                            for lang in languages:
                                try:
                                    translated_title[lang] = await g.translate(self.modal.event_title.value, lang)
                                except:
                                    translated_title[lang] = self.modal.event_title.value
                                try:
                                    translated_desc[lang] = await g.translate(self.modal.event_description.value, lang)
                                except:
                                    translated_desc[lang] = self.modal.event_description.value
                                try:
                                    translated_place[lang] = await g.translate(self.modal.event_place.value, lang)
                                except:
                                    translated_place[lang] = self.modal.event_place.value
                        
                        await interaction.response.edit_message(embed=embed, view=None)
                        await translate_all()

                        db.collection("events").document(id).set({
                            "title": translated_title,
                            "start": datetime.strptime(self.modal.event_date.value + " " + self.modal.event_time.value.split("-")[0], "%m/%d/%Y %H:%M"),
                            "end": datetime.strptime(self.modal.event_date.value + " " + self.modal.event_time.value.split("-")[1], "%m/%d/%Y %H:%M"),
                            "where": translated_place,
                            "desc": translated_desc,
                            "who": existing_event.get("who")
                        })

                        embed.set_footer(text="Status: confirmed")
                        embed.color = discord.Color.green()
                        
                        await interaction.followup.send("Event updated successfully!", ephemeral=True)
                        self.stop()

                    @discord.ui.button(label="Discard Event Changes 🗑️", style=discord.ButtonStyle.danger)
                    async def cancel_event(self, interaction: discord.Interaction, button: discord.ui.Button):
                        embed.set_footer(text="Status: cancelled")
                        embed.color = discord.Color.red()
                        await interaction.response.edit_message(embed=embed, view=None)
                        await interaction.followup.send("Event update cancelled!", ephemeral=True)
                        self.stop()

                view = EventChangesSubmissionView()

                await interaction.response.send_message(embed=embed, view=view)
                await view.wait()

        event_update_modal = EventUpdateModal()

        await interaction.response.send_modal(event_update_modal)

        
    
    @put.autocomplete("id")
    async def put_autocompletion_id(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> typing.List[app_commands.Choice[str]]:
        data = []
        for event in db.collection("events").stream():
            if current.lower() in event.id.lower():
                data.append(app_commands.Choice(name=event.id, value=event.id))
        return data




class EventCreationModal(discord.ui.Modal, title="Create an Event"):
    event_title = discord.ui.TextInput(
        style=discord.TextStyle.short,
        label="Title", 
        placeholder="Give your event a title",
        required=True
    )

    event_date = discord.ui.TextInput(
        style=discord.TextStyle.short,
        label="Date", 
        placeholder="MM/DD/YYYY",
        required=True
    )

    event_time = discord.ui.TextInput(
        style=discord.TextStyle.short,
        label="Start Time - End Time (24 Hour, EST Time)", 
        placeholder="HH:MM-HH:MM",
        required=True
    )

    event_place = discord.ui.TextInput(
        style=discord.TextStyle.short,
        label="Location",
        placeholder="Where is the event taking place?",
        required=True
    )

    event_description = discord.ui.TextInput(
        style=discord.TextStyle.long,
        label="Description", 
        placeholder="Give your event a description",
        max_length=1000,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        now = datetime.now()
        year = now.year
        month = now.month
        day = now.day
        hour = now.hour
        minute = now.minute

        embed = discord.Embed(
            title=f"Event Created @ {month}/{day}/{year} {hour}:{minute}EST",
            color=discord.Color.yellow(),
            
        )
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar)
        embed.add_field(name="Title", value=self.event_title.value, inline=True)
        embed.add_field(name="Date", value=self.event_date.value, inline=True)
        embed.add_field(name="Time", value=self.event_time.value, inline=True)
        embed.add_field(name="Location", value=self.event_place.value, inline=False)
        embed.add_field(name="Description", value=self.event_description.value, inline=False)
        embed.set_footer(text="Status: pending")
        
        class EventSubmissionView(discord.ui.View):
            modal = self
            @discord.ui.button(label="Confirm Event ✅", style=discord.ButtonStyle.success)
            async def confirm_event(self, interaction: discord.Interaction, button: discord.ui.Button):
                languages = db.collection('site').document('language_support').get().to_dict()['languages']
                translated_title = {}
                translated_desc = {}
                translated_place = {}
                async def translate_all():
                    
                    g = async_google_trans_new.AsyncTranslator()
                    for lang in languages:
                        try:
                            translated_title[lang] = await g.translate(self.modal.event_title.value, lang)
                        except:
                            translated_title[lang] = self.modal.event_title.value
                        try:
                            translated_desc[lang] = await g.translate(self.modal.event_description.value, lang)
                        except:
                            translated_desc[lang] = self.modal.event_description.value
                        try:
                            translated_place[lang] = await g.translate(self.modal.event_place.value, lang)
                        except:
                            translated_place[lang] = self.modal.event_place.value
                
                await interaction.response.edit_message(embed=embed, view=None)
                await translate_all()
                
                update_time, event_ref = db.collection("events").add({
                    "title": translated_title,
                    "start": datetime.strptime(self.modal.event_date.value + " " + self.modal.event_time.value.split("-")[0], "%m/%d/%Y %H:%M"),
                    "end": datetime.strptime(self.modal.event_date.value + " " + self.modal.event_time.value.split("-")[1], "%m/%d/%Y %H:%M"),
                    "where": translated_place,
                    "desc": translated_desc,
                    "who": []
                })

                embed.set_footer(text="Status: confirmed")
                embed.color = discord.Color.green()
                
                await interaction.followup.send(f"Event created successfully! ({event_ref.id})", ephemeral=True)
                self.stop()

            @discord.ui.button(label="Discard Event 🗑️", style=discord.ButtonStyle.danger)
            async def cancel_event(self, interaction: discord.Interaction, button: discord.ui.Button):
                embed.set_footer(text="Status: cancelled")
                embed.color = discord.Color.red()
                await interaction.response.edit_message(embed=embed, view=None)
                await interaction.followup.send("Event cancelled!", ephemeral=True)
                self.stop()

        view = EventSubmissionView()

        

        await interaction.response.send_message(embed=embed, view=view)
        await view.wait()


    async def on_error(self, interaction: discord.Interaction, error):
        print(error)


def run():
    if not settings.DISCORD_API_SECRET:
        print("Error: \'DISCORD_API_SECRET\' not set in .env file")
        return

    intents = discord.Intents.all()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        if not bot.user:
            return
        
        if not bot.user.id:
            return

        logger.info(f"User: {bot.user} (ID: {bot.user.id}) ")

        event_commands = EventsGroup(name="events", description="Commands for managing events")
        bot.tree.add_command(event_commands)

        bot.tree.copy_global_to(guild=settings.GUILD_ID)
        await bot.tree.sync(guild=settings.GUILD_ID)

    bot.run(settings.DISCORD_API_SECRET, root_logger=True)

if __name__ == "__main__":
    run()