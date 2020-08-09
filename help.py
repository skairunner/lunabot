from discord.ext.commands import HelpCommand

def help(args, brief, description):
    def help(command):
        command.brief = brief
        command.usage = args
        command.help = description
        return command
    return help