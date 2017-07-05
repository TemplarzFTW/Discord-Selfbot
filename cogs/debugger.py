import contextlib
import sys
import inspect
import os
import shutil
import appuselfbot
import glob
import math
from PythonGists import PythonGists
from discord.ext import commands
from io import StringIO
from cogs.utils.checks import *

# Common imports that can be used by the debugger.
import requests
import json
import gc
import datetime
import time
import traceback
import prettytable
import re
import io
import asyncio
import discord
import random
import subprocess
from bs4 import BeautifulSoup
import urllib
import psutil

'''Module for the python interpreter as well as saving, loading, viewing, etc. the cmds/scripts ran with the interpreter.'''


# Used to get the output of exec()
@contextlib.contextmanager
def stdoutIO(stdout=None):
    old = sys.stdout
    if stdout is None:
        stdout = StringIO()
    sys.stdout = stdout
    yield stdout
    sys.stdout = old


class Debugger:

    def __init__(self, bot):
        self.bot = bot

    # Executes/evaluates code. Got the idea from RoboDanny bot by Rapptz. RoboDanny uses eval() but I use exec() to cover a wider scope of possible inputs.
    async def interpreter(self, env, code):
        if code.startswith('[m]'):
            code = code[3:].strip()
            code_block = False
        else:
            code_block = True
        try:
            result = eval(code, env)
            if inspect.isawaitable(result):
                result = await result
            if not result:
                try:
                    with stdoutIO() as s:
                        result = exec(code, env)
                        if inspect.isawaitable(result):
                            result = await result
                    result = s.getvalue()
                except Exception as g:
                    return self.bot.bot_prefix + '```{}```'.format(type(g).__name__ + ': ' + str(g))
        except SyntaxError:
            try:
                with stdoutIO() as s:
                    result = exec(code, env)
                    if inspect.isawaitable(result):
                        result = await result
                result = s.getvalue()
            except Exception as g:
                return self.bot.bot_prefix + '```{}```'.format(type(g).__name__ + ': ' + str(g))

        except Exception as e:
            return self.bot.bot_prefix + '```{}```'.format(type(e).__name__ + ': ' + str(e))

        if len(str(result)) > 1950:
            url = PythonGists.Gist(description='Py output', content=str(result), name='output.txt')
            return self.bot.bot_prefix + 'Large output. Posted to Gist: %s' % url
        else:
            if code_block:
                return self.bot.bot_prefix + '```py\n{}\n```'.format(result)
            else:
                return result

    @commands.command(pass_context=True)
    async def debug(self, ctx, option: str = None):
        """Shows useful informations to people that try to help you."""
        try:
            if embed_perms(ctx.message):
                em = discord.Embed(color=0xad2929, title='\ud83e\udd16 Appu\'s Discord Selfbot Debug Infos')
                # em.add_field(name='Selfbot Version', value='%s'%self.bot.version)
                system = ''
                if sys.platform == 'linux':
                    system = subprocess.run(['uname', '-a'], stdout=subprocess.PIPE).stdout.decode('utf-8').strip()
                    if 'ubuntu' in os.lower():
                        system += '\n'+subprocess.run(['lsb_release', '-a'], stdout=subprocess.PIPE).stdout.decode('utf-8').strip()
                elif sys.platform == 'win32':
                    try: platform
                    except: import platform
                    system = '%s %s (%s)'%(platform.system(),platform.version(),sys.platform)
                    # os = subprocess.run('systeminfo | findstr /B /C:\"OS Name\" /C:\"OS Version\"', stdout=subprocess.PIPE).stdout.decode('utf-8').strip()
                else:
                    system = sys.platform
                em.add_field(name='Operating System', value='%s' % system)
                # em.add_field(name='Discord.py Version', value='%s'%discord.__version__)
                em.add_field(name='Python Version', value='%s (%s)'%(sys.version,sys.api_version))
                em.add_field(name='PIP Version', value='%s'%pkg_resources.get_distribution('pip').version)
                dependencies = ''
                dep_file = open('%s/requirements.txt' % os.getcwd()).read().split("\n")
                # [] + dep_file
                for dep in dep_file:
                    dep = dep.split('==')
                    cur = pkg_resources.get_distribution(dep[0]).version
                    if cur == dep[1]: dependencies += '\✅ %s: %s / %s\n'%(dep[0], cur, dep[1])
                    else: dependencies += '\❌ %s: %s / %s\n'%(dep[0], cur, dep[1])
                em.add_field(name='Dependencies', value='%s' % dependencies)
                if option and 'path' in option.lower():
                    paths = "\n".join(sys.path).strip()
                    if len(paths) > 500:
                        url = PythonGists.Gist(description='sys.path', content=str(paths), name='syspath.txt')
                        em.add_field(name='Import Paths', value=paths[:500]+' [(Show more)](%s)'%url)
                    else:
                        em.add_field(name='Import Paths', value=paths)
                user = subprocess.run(['whoami'], stdout=subprocess.PIPE).stdout.decode('utf-8').strip()
                if sys.platform == 'linux':
                    user += user+'@'+subprocess.run(['hostname'], stdout=subprocess.PIPE).stdout.decode('utf-8').strip()
                em.set_footer(text='Generated at {:%Y-%m-%d %H:%M:%S} by {}'.format(datetime.datetime.now(), user))
                try: await self.bot.send_message(ctx.message.channel, content=None, embed=em)
                except discord.errors.HTTPException as e:
                    await self.bot.send_message(ctx.message.channel, content=None, embed=em)
            else:
                await self.bot.send_message(ctx.message.channel, 'No permissions to embed debug info.')
            await self.bot.delete_message(ctx.message)
        except: await error(self.bot, ctx.message)

    @commands.group(pass_context=True)
    async def py(self, ctx):
        """Python interpreter. See the wiki for more info."""

        if ctx.invoked_subcommand is None:
            pre = cmd_prefix_len()
            code = ctx.message.content[2 + pre:].strip().strip('` ')

            env = {
                'bot': self.bot,
                'ctx': ctx,
                'message': ctx.message,
                'server': ctx.message.server,
                'channel': ctx.message.channel,
                'author': ctx.message.author
            }
            env.update(globals())

            result = await self.interpreter(env, code)

            os.chdir(os.getcwd())
            with open('%s/cogs/utils/temp.txt' % os.getcwd(), 'w') as temp:
                temp.write(ctx.message.content[2 + pre:].strip())

            await self.bot.send_message(ctx.message.channel, result)

    # Save last >py cmd/script.
    @py.command(pass_context=True)
    async def save(self, ctx, *, msg):
        """Save the code you last ran. Ex: >py save stuff"""
        msg = msg.strip()[:-4] if msg.strip().endswith('.txt') else msg.strip()
        os.chdir(os.getcwd())
        if not os.path.exists('%s/cogs/utils/temp.txt' % os.getcwd()):
            return await self.bot.send_message(ctx.message.channel, self.bot.bot_prefix + 'Nothing to save. Run a ``>py`` cmd/script first.')
        if not os.path.isdir('%s/cogs/utils/save/' % os.getcwd()):
            os.makedirs('%s/cogs/utils/save/' % os.getcwd())
        if os.path.exists('%s/cogs/utils/save/%s.txt' % (os.getcwd(), msg)):
            await self.bot.send_message(ctx.message.channel, self.bot.bot_prefix + '``%s.txt`` already exists. Overwrite? ``y/n``.' % msg)
            reply = await self.bot.wait_for_message(author=ctx.message.author)
            if reply.content.lower().strip() != 'y':
                return await self.bot.send_message(ctx.message.channel, self.bot.bot_prefix + 'Cancelled.')
            if os.path.exists('%s/cogs/utils/save/%s.txt' % (os.getcwd(), msg)):
                os.remove('%s/cogs/utils/save/%s.txt' % (os.getcwd(), msg))

        try:
            shutil.move('%s/cogs/utils/temp.txt' % os.getcwd(), '%s/cogs/utils/save/%s.txt' % (os.getcwd(), msg))
            await self.bot.send_message(ctx.message.channel, self.bot.bot_prefix + 'Saved last run cmd/script as ``%s.txt``' % msg)
        except:
            await self.bot.send_message(ctx.message.channel, self.bot.bot_prefix + 'Error saving file as ``%s.txt``' % msg)

    # Load a cmd/script saved with the >save cmd
    @py.command(aliases=['start'], pass_context=True)
    async def run(self, ctx, *, msg):
        """Run code that you saved with the save commmand. Ex: >py run stuff parameter1 parameter2"""
        # Like in unix, the first parameter is the script name
        parameters = msg.split()
        save_file = parameters[0] # Force scope
        if save_file.endswith('.txt'): 
            save_file = save_file[:-(len('.txt'))] # Temptation to put '.txt' in a constant increases
        else:
            parameters[0] += '.txt' # The script name is always full
        
        if not os.path.exists('%s/cogs/utils/save/%s.txt' % (os.getcwd(), save_file)):
            return await self.bot.send_message(ctx.message.channel, self.bot.bot_prefix + 'Could not find file ``%s.txt``' % save_file)

        script = open('%s/cogs/utils/save/%s.txt' % (os.getcwd(), save_file)).read()

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'message': ctx.message,
            'server': ctx.message.server,
            'channel': ctx.message.channel,
            'author': ctx.message.author,
            'argv': parameters
        }
        env.update(globals())

        result = await self.interpreter(env, script.strip('` '))

        await self.bot.send_message(ctx.message.channel, result)

    # List saved cmd/scripts
    @py.command(aliases=['ls'], pass_context=True)
    async def list(self, ctx, txt: str = None):
        """List all saved scripts. Ex: >py list or >py ls"""
        os.chdir('%s/cogs/utils/save/' % os.getcwd())
        try:
            if txt:
                numb = txt.strip()
                if numb.isdigit():
                    numb = int(numb)
                else:
                    await self.bot.send_message(ctx.message.channel, self.bot.bot_prefix + 'Invalid syntax. Ex: ``>py list 1``')
            else:
                numb = 1
            filelist = glob.glob('*.txt')
            if len(filelist) == 0:
                return await self.bot.send_message(ctx.message.channel, self.bot.bot_prefix + 'No saved cmd/scripts.')
            filelist.sort()
            msg = ''
            pages = int(math.ceil(len(filelist) / 10))
            if numb < 1:
                numb = 1
            elif numb > pages:
                numb = pages

            for i in range(10):
                try:
                    msg += filelist[i + (10 * (numb-1))] + '\n'
                except:
                    break

            await self.bot.send_message(ctx.message.channel, self.bot.bot_prefix + 'List of saved cmd/scripts. Page ``%s of %s`` ```%s```' % (numb, pages, msg))
        except Exception as e:
            await self.bot.send_message(ctx.message.channel, self.bot.bot_prefix + 'Error, something went wrong: ``%s``' % e)
        finally:
            os.chdir('..')
            os.chdir('..')
            os.chdir('..')

    # View a saved cmd/script
    @py.group(aliases=['vi', 'vim'], pass_context=True)
    async def view(self, ctx, *, msg: str):
        """View a saved script's contents. Ex: >py view stuff"""
        msg = msg.strip()[:-4] if msg.strip().endswith('.txt') else msg.strip()
        os.chdir('%s/cogs/utils/save/' % os.getcwd())
        try:
            if os.path.exists('%s.txt' % msg):
                f = open('%s.txt' % msg, 'r').read()
                await self.bot.send_message(ctx.message.channel, self.bot.bot_prefix + 'Viewing ``%s.txt``: ```%s```' % (msg, f.strip('` ')))
            else:
                await self.bot.send_message(ctx.message.channel, self.bot.bot_prefix + '``%s.txt`` does not exist.' % msg)

        except Exception as e:
            await self.bot.send_message(ctx.message.channel, self.bot.bot_prefix + 'Error, something went wrong: ``%s``' % e)
        finally:
            os.chdir('..')
            os.chdir('..')
            os.chdir('..')

    # Delete a saved cmd/script
    @py.group(aliases=['rm'], pass_context=True)
    async def delete(self, ctx, *, msg: str):
        """Delete a saved script. Ex: >py delete stuff"""
        msg = msg.strip()[:-4] if msg.strip().endswith('.txt') else msg.strip()
        os.chdir('%s/cogs/utils/save/' % os.getcwd())
        try:
            if os.path.exists('%s.txt' % msg):
                os.remove('%s.txt' % msg)
                await self.bot.send_message(ctx.message.channel, self.bot.bot_prefix + 'Deleted ``%s.txt`` from saves.' % msg)
            else:
                await self.bot.send_message(ctx.message.channel, self.bot.bot_prefix + '``%s.txt`` does not exist.' % msg)
        except Exception as e:
            await self.bot.send_message(ctx.message.channel, self.bot.bot_prefix + 'Error, something went wrong: ``%s``' % e)
        finally:
            os.chdir('..')
            os.chdir('..')
            os.chdir('..')


    @commands.command(pass_context=True)
    async def load(self, ctx, *, msg):
        """Load a module"""
        try:
            self.bot.load_extension(msg)
        except Exception as e:
            try:
                self.bot.load_extension('cogs.'+msg)
            except:
                await error(self.bot, ctx.message)
                await self.bot.send_message(ctx.message.channel, '``` {}: {} ```'.format(type(e).__name__, e))
                return
        await success(self.bot,ctx.message)
        await asyncio.sleep(10)
        await self.bot.delete_message(ctx.message)


    @commands.command(pass_context=True)
    async def unload(self, ctx, *, msg):
        """Unload a module"""
        try:
            self.bot.unload_extension(msg)
        except Exception as e:
            try:
                self.bot.unload_extension('cogs.'+msg)
            except:
                await error(self.bot, ctx.message)
                await self.bot.send_message(ctx.message.channel, '``` {}: {} ```'.format(type(e).__name__, e))
                return
        await success(self.bot,ctx.message)
        await asyncio.sleep(10)
        await self.bot.delete_message(ctx.message)


def setup(bot):
    bot.add_cog(Debugger(bot))
