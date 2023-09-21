Using tygra
===========
 
.. contents::
   :local:
   :backlinks: none

Requirements
------------

*Tygra* was developed on the Mac. It as **not** been tested on any other platforms.  Since it uses *tkinter*
extensively, it is unlikely it will work under other platforms.  If you want to help with it's extension 
to work with other platforms, it would be appreciated.

So, for now the requirements are:

* Mac/OS
* Python 3.11 (uses Self)
* matplotlib

Installing tygra
----------------

As a module
^^^^^^^^^^^

To install matplotlib:

.. code-block::

   pip3 install matplotlib
    
As a Mac/OS app
^^^^^^^^^^^^^^^
 
Tygra is also built as a Mac .app as well.
 
Details TBA.


Running tygra
-------------

The tygra package must be in the Python search path.  One way to do this is to put it in the *PYTHONPATH*
environment variable:

.. code-block::
   :caption: Mac
   
   env PYTHONPATH=/path/to/directory/containing/tygra:$PYHTONPATH


See `Python documentation, 1.2 Environment Variables <https://docs.python.org/3/using/cmdline.html#environment-variables>`_ 
for more detail.

As a module
^^^^^^^^^^^

Run tygra as follows:

.. code-block::

   python3 -m tygra

As a Mac/OS app
^^^^^^^^^^^^^^^

Just click on the app icon |tygraIcon| in Mac/OS Finder.

.. |tygraIcon| image:: images/tygra-logo-small.png
	:height: 20
	:width: 20


Getting started
---------------

Normally, *tygra* remembers what you were doing when it was last run.  However, the first time you use *tygra*
it doesn't have that information, so it will bring up an "open file" dialog.  You can just chose the **cancel**
button to start a new file. *Tygra* will then open a file window and a new view window, like this:

.. figure:: images/newFile.png

There is no name for the new model or its new view; you can fill that in with whatever name you want.

.. note:: Model and view names can be anything you want, and can event be duplicated because, internally, 
	*tygra* doesn't depend on names, but rather uses internal IDs for references. You can also change model
	and view names without having to worry that will mess up references.

Notice that there is a small (expandable) text section at the button of both types of windows.  This is for 
informational and error text. Because *tygra* is typed, there are lots of possible errors that it catches,
and these are reported here rather than annoying error dialog boxes. 

.. note:: One somewhat annoying feature is that
   there are **two** places where errors may be logged: in the file window and in the view window. The reason
   for this annoyance is that models know nothing about their views, so if a message arises from an occurrence
   in a model, the model has no access to the current view, so it must log the message to the file window.

To start creating a graph, right-click the background of the view window and choose "new node", which brings
a submenu of all the possible node types.  There is only one type available initially:

.. figure:: images/firstNode.png

Choosing "T" ("Top node") will bring up a new node (represented as a white box) and an "attributes editor"
dialog box:

.. figure:: images/newNodeDialog.png

From there, you edit the attributes of your new node, such as its *label*\ , shape, and fill, text, and border
colours. You will notice that there are two sections in the editor dialog: *Local* and *Interited*\ . Recall from
the concepts page, :ref:`concepts.types`, that all nodes and relations are typed, so *Local* section contains 
attributes that are either defined in the current node/relation or defined by a supertype and overridden in the
current node/relation. *Interited* attributes are inherited from some supertype of the current node/relation.
You may change the values of either, but in the case of inherited attributes, not until you explicitly override
the attribute.


