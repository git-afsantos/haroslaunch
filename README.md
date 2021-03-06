# HAROS Launch File Parser

This package provides a parser and interpreter for [ROS launch XML files](http://wiki.ros.org/roslaunch/XML).

## Installing

Installing a pre-packaged release:

```bash
pip install haroslaunch
```

Installing from source:

```bash
git clone https://github.com/git-afsantos/haroslaunch.git
cd haroslaunch
pip install -e .
```

## Usage

When used as a library, you can generate runtime models of the entities that would be created/launched when executing launch files with the standard `roslaunch` tool.
For example:

```python
from pathlib import Path
from haroslaunch.launch_interpreter import LaunchInterpreter
from haroslaunch.ros_iface import SimpleRosInterface

fp = Path('path/to/file.launch')
iface = SimpleRosInterface()
rli = LaunchInterpreter(iface)
rli.interpret(fp)
print(rli.rosparam_cmds)
print(rli.parameters)
print(rli.nodes)
print(rli.machines)
```

## Bugs, Questions and Support

Please use the [issue tracker](https://github.com/git-afsantos/haroslaunch/issues).

## Contributing

See [CONTRIBUTING](./CONTRIBUTING.md).
