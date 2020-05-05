"""
Minimal and functional version of CPython's argparse module.
"""

import sys
try:
    from ucollections import namedtuple
except ImportError:
    from collections import namedtuple


class _ArgError(BaseException):
    pass


class _Arg:
    def __init__(self, names, dest, metavar, arg_type, action, nargs, const, default, required, choices, help):
        self.names = names
        self.dest = dest
        self.metavar = metavar
        self.arg_type = arg_type
        self.action = action
        self.nargs = nargs
        self.const = const
        self.default = default
        self.required = required
        self.choices = choices
        self.help = help

    def parse(self, optname, args):
        # parse args for this Arg
        def _checked(_arg):
            if self.choices and _arg not in self.choices:
                raise _ArgError("value %s must be one of this '%s'" % (_arg, ', '.join(map(str, self.choices))))
            try:
                return self.arg_type(_arg)
            except (TypeError, ValueError, OSError):
                try:
                    raise _ArgError('invalid %s value: %s' % (self.arg_type.__name__, _arg))
                except AttributeError:
                    raise _ArgError('value %s is not applicable for type of key %s' % (_arg, optname))

        if self.action == "store" or self.action == "append":
            if self.nargs is None:
                if args:
                    return _checked(args.pop(0))
                else:
                    raise _ArgError("expecting value for %s" % optname)
            elif self.nargs == "?":
                if args:
                    return _checked(args.pop(0))
                else:
                    return self.default
            else:
                if self.nargs == "*":
                    n = -1
                elif self.nargs == "+":
                    if not args:
                        raise _ArgError("expecting value for %s" % optname)
                    n = -1
                else:
                    n = int(self.nargs)
                ret = []
                stop_at_opt = True
                while args and n != 0:
                    if stop_at_opt and args[0].startswith("-") and args[0] != "-":
                        if args[0] == "--":
                            stop_at_opt = False
                            args.pop(0)
                        else:
                            break
                    else:
                        ret.append(_checked(args.pop(0)))
                        n -= 1
                if n > 0:
                    raise _ArgError("expecting value for %s" % optname)
                return ret
        elif self.action == "store_const":
            return self.const
        elif self.action == "append":
            if args:
                return _checked(args.pop(0))
            else:
                raise _ArgError("expecting value for %s" % optname)
        else:
            assert False


def _dest_from_optnames(opt_names):
    dest = opt_names[0]
    for name in opt_names:
        if name.startswith("--"):
            dest = name
            break
    return dest.lstrip("-").replace("-", "_")


class ArgumentParser:
    def __init__(self, *, prog=sys.argv[0], description="", epilog=""):
        self.prog = prog
        self.description = description
        self.epilog = epilog
        self.opt = []
        self.pos = []

    def add_argument(self, *args, **kwargs):
        action = kwargs.get("action", "store")
        if action == "store_true":
            action = "store_const"
            const = True
            default = kwargs.get("default", False)
        elif action == "store_false":
            action = "store_const"
            const = False
            default = kwargs.get("default", True)
        else:
            const = kwargs.get("const", None)
            default = kwargs.get("default", None)
        if args and args[0].startswith("-"):
            list = self.opt
            dest = kwargs.get("dest")
            if dest is None:
                dest = _dest_from_optnames(args)
        else:
            list = self.pos
            dest = kwargs.get("dest")
            if dest is None:
                dest = args[0]
            if not args:
                args = [dest]
        arg_type = kwargs.get("type", str)
        nargs = kwargs.get("nargs", None)
        metavar = kwargs.get("metavar", None)
        required = kwargs.get("required", False)
        choices = kwargs.get("choices", None)
        help = kwargs.get("help", "")
        list.append(
            _Arg(args, dest, metavar, arg_type, action, nargs, const, default, required, choices, help))

    def usage(self, full):
        # print short usage
        print("usage: %s [-h, --help]" % self.prog, end="")

        def render_arg(arg):
            if arg.action in ["store", "append"]:
                if arg.metavar:
                    arg_for_render = "%s" % arg.metavar.upper()
                elif arg.choices:
                    arg_for_render = "[%s]" % ", ".join(arg.choices)
                else:
                    arg_for_render = arg.dest.upper()
                if arg.nargs is None:
                    return " %s" % arg_for_render
                if isinstance(arg.nargs, int):
                    return " %s(x%d)" % (arg_for_render, arg.nargs)
                else:
                    return " [%s...]" % arg_for_render
            else:
                return ""
        for opt in self.opt:
            print(" [%s%s]" % (', '.join(opt.names), render_arg(opt)), end="")
        for pos in self.pos:
            print(render_arg(pos), end="")
        print()

        if not full:
            return

        # print full information
        print()
        if self.description:
            print(self.description)
        if self.pos:
            print("\nPositional arguments:")
            for pos in self.pos:
                print("  %-20s%s" % (pos.names[0], pos.help))
        print("\nNamed arguments:")
        print("  -h, --help          show this message and exit")
        for opt in self.opt:
            # Dont show help with possible values for opt. It's stays in "usage" anyway.
            # print("  %-20s%s " % (', '.join(opt.names) + render_arg(opt).upper(), opt.help))
            print("  %-20s%s" % (', '.join(opt.names), opt.help))

        print("\n", self.epilog)

    def parse_args(self, args=None):
        return self._parse_args_impl(args, False)

    def parse_known_args(self, args=None):
        return self._parse_args_impl(args, True)

    def _parse_args_impl(self, args, return_unknown):
        if args is None:
            args = sys.argv[1:]
        else:
            args = args[:]
        try:
            return self._parse_args(args, return_unknown)
        except _ArgError as e:
            self.usage(False)
            print("error:", e)
            sys.exit(2)

    def _parse_args(self, args, return_unknown):
        # add optional(named) args with defaults
        arg_dest = []
        arg_vals = []
        for opt in self.opt:
            arg_dest.append(opt.dest)
            arg_vals.append(opt.default)

        # deal with unknown arguments, if needed
        unknown = []
        def consume_unknown():
            while args and not args[0].startswith("-"):
                unknown.append(args.pop(0))

        # parse all args
        parsed_pos = False
        while args or not parsed_pos:
            if args and args[0].startswith("-") and args[0] != "-" and args[0] != "--":
            # optional(named) arguments
                a = args.pop(0)
                if a in ("-h", "--help"):
                    self.usage(True)
                    sys.exit(0)
                found = False
                for i, opt in enumerate(self.opt):
                    if a in opt.names:
                        if opt.action == "append":
                            if type(arg_vals[i]) is type(None):
                                arg_vals[i] = []
                            arg_vals[i].append(opt.parse(a, args))
                            found = True
                        else:
                            arg_vals[i] = opt.parse(a, args)
                            found = True
                            break
                if not found:
                    if return_unknown:
                        unknown.append(a)
                        consume_unknown()
                    else:
                        raise _ArgError("unknown option %s" % a)
            else:
            # positional arguments
                if parsed_pos:
                    if return_unknown:
                        unknown = unknown + args
                        break
                    else:
                        raise _ArgError("extra args: %s" % " ".join(args))
                for pos in self.pos:
                    arg_dest.append(pos.dest)
                    arg_vals.append(pos.parse(pos.names[0], args))
                parsed_pos = True
                if return_unknown:
                    consume_unknown()

        # checks the required arguments
        required_but_not_used = ([arg.dest for i, arg in enumerate(self.opt) if arg.required == True and arg_vals[i] == None])
        if required_but_not_used:
            raise _ArgError("option(s) '%s' is(are) required" % ", ".join(required_but_not_used))

        values = namedtuple("args", arg_dest)(*arg_vals)
        return (values, unknown) if return_unknown else values
