import os
import warnings
from typing import Any, Optional, Union

import click
from appdirs import AppDirs  # 用于跨平台的应用程序目录路径管理
from loguru import logger  # 用于日志记录
from rich.console import Console  # 用于终端美化输出

from . import iface

warnings.filterwarnings("ignore")  # 忽略所有警告

console = Console()  # 创建一个控制台对象，用于美化输出


def decrypt(config: iface.Config, ctext: Any) -> Union[str, bytes]:
    """一个简单的别名函数，用于搜索密文并使答案更美观"""
    res: Optional[iface.SearchResult] = config.objs["searcher"].search(ctext)
    if res is None:
        return "Failed to crack"  # 如果没有找到结果，返回"Failed to crack"
    if config.verbosity < 0:
        return res.path[-1].result.value  # 如果详细级别小于0，返回最终结果的值
    else:
        return iface.pretty_search_results(res)  # 否则，返回美化后的搜索结果


def get_name(ctx, param, value):
    # 如果没有提供参数值，则从标准输入读取
    if not value and not click.get_text_stream("stdin").isatty():
        click.get_text_stream("stdin").read().strip()
        return click.get_text_stream("stdin").read().strip()
    else:
        return value  # 否则返回参数值


def print_help(ctx):
    # 打印帮助菜单
    # 如果没有传递参数，则打印帮助菜单并退出
    click.echo(ctx.get_help())
    ctx.exit()


@click.command()
@click.option(
    "-t",
    "--text",
    help="你想要解密的密文。",
    type=str,
)
@click.option(
    "-q", "--quiet", help="减少详细级别", type=int, count=True, default=None
)
@click.option(
    "-g",
    "--greppable",
    help="仅打印答案（对grep有用）",
    type=bool,
    is_flag=True,
    default=None,
)
@click.option("-v", "--verbose", count=True, type=int)
@click.option("-C", "--checker", help="使用指定的检查器", default=None)
@click.option(
    "-c",
    "--config",
    help="使用指定的配置文件。默认为 appdirs.user_config_dir('ciphey', 'ciphey')/'config.yml'",
)
@click.option("-w", "--wordlist", help="使用指定的单词列表")
@click.option(
    "-p",
    "--param",
    help="传递参数给语言检查器",
    multiple=True,
)
@click.option(
    "-l",
    "--list-params",
    help="列出所选模块的参数",
    type=bool,
)
@click.option(
    "--searcher",
    help="选择要使用的搜索算法",
)
@click.option(
    "-b",
    "--bytes",
    help="强制ciphey使用二进制模式输入",
    is_flag=True,
    default=None,
)
@click.option(
    "--default-dist",
    help="设置默认的字符/字节分布",
    type=str,
    default=None,
)
@click.option(
    "-m",
    "--module",
    help="从给定路径添加模块",
    type=click.Path(),
    multiple=True,
)
@click.option(
    "-A",
    "--appdirs",
    help="打印Ciphey期望的设置文件位置",
    type=bool,
    is_flag=True,
)
@click.option("-f", "--file", type=click.File("rb"), required=False)
@click.argument("text_stdin", callback=get_name, required=False)
def main(**kwargs):
    """Ciphey - 自动解密工具

    文档:
    https://github.com/Ciphey/Ciphey/wiki\n
    支持（我们大部分时间在线）:
    https://discord.ciphey.online/\n
    GitHub:
    https://github.com/ciphey/ciphey\n

    Ciphey 是一个使用智能人工智能和自然语言处理的自动解密工具。输入加密文本，返回解密文本。

    示例:\n
        基本用法: ciphey -t "aGVsbG8gbXkgbmFtZSBpcyBiZWU="
    """

    # 如果用户想知道appdirs的位置
    # 打印并退出
    if "appdirs" in kwargs and kwargs["appdirs"]:
        dirs = AppDirs("Ciphey", "Ciphey")
        path_to_config = dirs.user_config_dir
        print(
            f"The settings.yml file should be at {os.path.join(path_to_config, 'settings.yml')}"
        )
        return None

    # 现在我们创建配置对象
    config = iface.Config()

    # 将设置文件加载到配置中
    load_msg: str
    cfg_arg = kwargs["config"]
    if cfg_arg is None:
        # 确保配置目录确实存在
        os.makedirs(iface.Config.get_default_dir(), exist_ok=True)
        config.load_file(create=True)
        load_msg = f"打开配置文件 {os.path.join(iface.Config.get_default_dir(), 'config.yml')}"
    else:
        config.load_file(cfg_arg)
        load_msg = f"打开配置文件 {cfg_arg}"

    # 加载详细级别，以便我们可以开始记录日志
    verbosity = kwargs["verbose"]
    quiet = kwargs["quiet"]
    if verbosity is None:
        if quiet is not None:
            verbosity = -quiet
    elif quiet is not None:
        verbosity -= quiet
    if kwargs["greppable"] is not None:
        verbosity -= 999
    # 使用现有值作为基准
    config.verbosity += verbosity
    config.update_log_level(config.verbosity)
    logger.debug(load_msg)
    logger.trace(f"获取命令行参数 {kwargs}")

    # 现在加载模块
    module_arg = kwargs["module"]
    if module_arg is not None:
        config.modules += list(module_arg)

    # 我们需要在实例化对象之前加载格式
    if kwargs["bytes"] is not None:
        config.update_format("bytes")

    # 接下来，加载对象
    params = kwargs["param"]
    if params is not None:
        for i in params:
            key, value = i.split("=", 1)
            parent, name = key.split(".", 1)
            config.update_param(parent, name, value)
    config.update("checker", kwargs["checker"])
    config.update("searcher", kwargs["searcher"])
    config.update("default_dist", kwargs["default_dist"])

    config.complete_config()

    logger.trace(f"命令行选项: {kwargs}")
    logger.trace(f"配置完成: {config}")

    # 最后，加载明文
    if kwargs["text"] is None:
        if kwargs["file"] is not None:
            kwargs["text"] = kwargs["file"].read()
        elif kwargs["text_stdin"] is not None:
            kwargs["text"] = kwargs["text_stdin"]
        else:
            # 否则打印帮助菜单
            print("[bold red]错误。没有输入提供给Ciphey. [bold red]")

            @click.pass_context
            def all_procedure(ctx):
                print_help(ctx)

            all_procedure()

            return None

    if issubclass(config.objs["format"], type(kwargs["text"])):
        pass
    elif config.objs["format"] == str and isinstance(kwargs["text"], bytes):
        kwargs["text"] = kwargs["text"].decode("utf-8")
    elif config.objs["format"] == bytes and isinstance(kwargs["text"], str):
        kwargs["text"] = kwargs["text"].encode("utf-8")
    else:
        raise TypeError(f"无法从 {type(kwargs['text'])} 加载类型 {config.format}")

    result: Optional[str]

    # 如果启用了调试或安静模式，则在没有旋转指示器的情况下运行
    if config.verbosity != 0:
        result = decrypt(config, kwargs["text"])
    else:
        # 否则，如果详细级别为0，则使用旋转指示器运行
        with console.status("[bold green]思考中...", spinner="moon") as status:
            config.set_spinner(status)
            result = decrypt(config, kwargs["text"])
    if result is None:
        result = "无法找到任何解决方案。"

    console.print(result)  # 打印最终解密结果
