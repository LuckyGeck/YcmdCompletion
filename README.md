YcmdCompletion
==============

Sublime Text 3 plugin for code completion and error highlighting, based on [Ycmd server](https://github.com/Valloric/ycmd)

## Installation
  Simply use Package Control and Install Package `YcmdCompletion`.
  Direct [link](https://sublime.wbond.net/packages/YcmdCompletion) to plugin in sublime packages repository.

## Post-Install

1. Open default settings to see, what options are available.
  To open default settings, you can use Sublime Text menu:

  `Preferences > Package Settings > YcmdCompletion > Settings - Default`

2. To set your personal settings, use User Settings file:

  `Preferences > Package Settings > YcmdCompletion > Settings - User`

3. Prepare `Ycmd Server` (clone to your machine and build) as it is described [here](https://github.com/Valloric/ycmd#building)

Note that you need to enable Rust/Go support explicitly by adding them to the `languages` array in the settings file. Other languages mentioned in the default settings file may also work, however this plugin has only been tested with these. For Rust and Go to work you must have compiled ycmd with the appropriate options, check out the docs for more information. This is true for most other ycmd-supported languages as well.

###Option 1:
4.1 Generate your personal [HMAC](https://github.com/Valloric/ycmd#is-hmac-auth-for-requestsresponses-really-necessary) key.
  It can be done by executing additional command:

  `Command Palette > Ycmd: Create HMAC keys`
  
  It will be automaticaly written down to your plugin's settings. Just copy-n-paste it to settings of `ycmd`.

5.1 Run `ycmd` with your settings. You can find [this article](https://github.com/Valloric/ycmd#user-level-customization) useful. 

6 Open any `*.cpp` or `*.py` file and try to use auto-completion.

###Option 2:
4.2 Go to your personal settings and set `use_auto_start_localserver` to 1

5.2 Set `ycmd_path` to point to your local installation of Ycmd Server (e.g.:`home/USERNAME/ycmd/ycmd`), and either provide the location to your settings file for the ycmd Server or ignore `default_settings_path` to use the default file that comes with ycmd.

6 Open any `*.cpp` or `*.py` file and try to use auto-completion.

## Functions

YcmdCompletion now supports three new handy functions!

1. `GoTo` goes to the definition of the variable under the cursor. If it's a type that the cursor is on, `GoTo` automatically recognizes that and instead opens the file that contains the declaration and jumps to the corresponding point.
2. `GeType` shows the type of the Object in the statusbar.
3. `GetParent` shows the enclosing function in the statusbar.

**Please note that the cursor must be in front of or somewhere in the word you are calling the function for.**

## FAQ

Feel free to email me with any questions about this plugin. Questions with answers are placed [here](https://github.com/LuckyGeck/YcmdCompletion/wiki/FAQ).

## Miscellaneous enhancements

By default, Sublime only shows the autocomplete dialog when you have started typing a word. This means that field and path autocompletion only occur after you type the first character of the field or path (e.g. only after typing `x` in `foo::x` or `foo.x`). To make it appear when you have typed `foo::` or `foo.` and show the full range of path/field/method autocompletions, you need to add a syntax-specific config file to Sublime.

To do this, open a file of the language you wish to tweak, go to `Preferences -> Settings - More -> Syntax Specific - User`, and add an autocomplete specification like so:

```
{
    "auto_complete_selector": "source - (comment, string.quoted)",
    "auto_complete_triggers": [
        {"selector": "source.c++", "characters": "."},
        {"selector": "source.c++", "characters": "::"},
        {"selector": "source.c++", "characters": "->"}
    ]
}
``` 

The ` - (comment, string.quoted)` means that autocompletion will not complete within comments or strings (you can remove this if you don't need it). Depending on your language, you may need to modify the triggers.

## License

Copyright 2014 [Pavel Sychev](pasha.sychev@gmail.com). Licensed under the MIT License
