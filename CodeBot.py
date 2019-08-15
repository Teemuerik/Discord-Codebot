# -*- coding: utf-8 -*-

import asyncio
import discord
import json
import os

from discord.ext import commands
from discord.utils import get

TOKEN = "NjEwNzkwMDk0NjA5MDU1Nzc3.XVKZ2g.QPtPHeZ4mAm1vT9Y3EVqzWQcsGw"

owner = "Mäntänmakkara#5107"

bot = commands.Bot(command_prefix="$")

role_msg_content = "Valitse rooleja:"

class ServerConfig:
    role_reactions = {}

    async def to_json(self):
        data = {}
        data["role_reactions"] = self.role_reactions
        return data
    
    @staticmethod
    async def from_json(data):
        config = ServerConfig()
        config.role_reactions = data["role_reactions"]
        return config

async def get_config(guild_id) -> ServerConfig:
    config = ServerConfig()
    fn = str(guild_id) + ".json"
    if os.path.exists(fn):
        with open(fn, "r") as f:
            config = await ServerConfig.from_json(json.load(f))
    return config

async def set_config(config, guild_id):
    with open(str(guild_id) + ".json", "w") as f:
        json.dump(await config.to_json(), f)

@bot.command(name="role_message", pass_context=True)
@commands.has_permissions(administrator=True)
async def send_role_message(ctx):
    await ctx.message.delete()
    await ctx.send(role_msg_content)

async def add_role_reaction(member: discord.Member, channel: discord.TextChannel, reaction, guild: discord.Guild):
    check = lambda m: m.author == member
    msgs = []
    while True:
        msgs.append(await channel.send(f"Kirjoita roolin nimi reaktiolle :{reaction}:"))
        msg: discord.Message = await bot.wait_for('message', check=check)
        msgs.append(msg)
        if msg.content in [r.name for r in guild.roles]:
            print("Role found in guild roles...")
            for m in msgs:
                await m.delete()
            break
        else:
            print(f"Role \"{msg.content}\" not found.")
            msgs.append(await channel.send(f"Roolia \"{msg.content}\" ei ole tällä palvelimella."))
    print("Adding role to config...")
    config = await get_config(guild.id)
    config.role_reactions[reaction] = get(guild.roles, name=msg.content).id
    await set_config(config, guild.id)

@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    config = await get_config(payload.guild_id)
    channel: discord.TextChannel = bot.get_channel(payload.channel_id)
    user: discord.User = bot.get_user(payload.user_id)
    member: discord.Member = [m for m in channel.members if m.discriminator == user.discriminator][0]
    if payload.emoji.name not in config.role_reactions.keys():
        if member.guild_permissions.administrator:
            print("Prompting role add...")
            await add_role_reaction(member, channel, payload.emoji.name, bot.get_guild(payload.guild_id))
            return
        else:
            print("User can't add reactions, removing reaction...")
            return
    msg: discord.Message = await channel.fetch_message(payload.message_id)
    if msg.content == role_msg_content:
        role: discord.Role = get(member.guild.roles, id=config.role_reactions[payload.emoji.name])
        print(f"Adding role \"{role.name}\" to member \"{member.display_name}#{member.discriminator}\"")
        await member.add_roles(role)

@bot.event
async def on_raw_reaction_remove(payload):
    config = await get_config(payload.guild_id)
    channel: discord.TextChannel = bot.get_channel(payload.channel_id)
    user: discord.User = bot.get_user(payload.user_id)
    member: discord.Member = [m for m in channel.members if m.discriminator == user.discriminator][0]
    msg: discord.Message = await channel.fetch_message(payload.message_id)
    if msg.content == role_msg_content:
        role: discord.Role = get(member.guild.roles, id=config.role_reactions[payload.emoji.name])
        print(f"Removing role \"{role.name}\" from member \"{member.display_name}#{member.discriminator}\"")
        await member.remove_roles(role)

@bot.event
async def on_member_join(member: discord.Member):
    role: discord.Role = get(member.guild.roles, name="Code Monkey")
    print(f"Adding default role to member \"{member.display_name}#{member.discriminator}\"")
    await member.add_roles(role)

bot.run(TOKEN)