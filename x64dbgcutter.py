import cutter

import os, sqlite3, traceback, json, base64

import PySide2.QtWidgets as QtWidgets

BPNORMAL = 0,
BPHARDWARE = 1,
BPMEMORY = 2,
BPDLL = 3,
BPEXCEPTION = 4

class x64dbgCutter(object):
    def __init__(self, plugin, main):
        self.plugin = plugin
        self.main = main
        self._last_directory = None
        
    def load(self):
        action = QtWidgets.QAction("x64dbg - Import database", self.main)
        action.triggered.connect(self.import_db)
        self.main.addMenuFileAction(action)
        
        action = QtWidgets.QAction("x64dbg - Export database", self.main)
        action.triggered.connect(self.export_db)
        self.main.addMenuFileAction(action)
        cutter.message("[w64dbg-cutter] Initialized")

    def unload(self):
        pass

    def file_dialog(self, title, new=False):
        file_dialog = QtWidgets.QFileDialog(
            self.main,
            title,
            self._last_directory,
            'Databases (*.dd64)'
        )

        if new:
            file_dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
            filename = file_dialog.getOpenFileName()[0]
        else:
            filename = file_dialog.getSaveFileName()[0]

        # Remember the last directory we were in (parsed from a selected file)
        # for the next time the user comes to load coverage files
        if filename:
            self._last_directory = os.path.dirname(filename) + os.sep

        cutter.message("[w64dbg-cutter] Received filename from file dialog:")
        cutter.message(" - %s" % filename)

        return filename

    def export_db(self):
        filename = self.file_dialog("Open new file for export")
        if not filename:
            return

        cutter.message("[x64dbg-cutter]: Exporting database to %s" % filename)
        
        db = {}
        
        base_addr = cutter.cmdj("evj bin.baddr")[0]["value"]
        cutter.message("[x64dbg-cutter]: baddr is %d" % base_addr)
        
        # We can only export items from the main binary currently
        module = os.path.basename(cutter.cmdj("ij")["core"]["file"]).lower()
        
        # r2: {"addr":5368778842,"size":1,"prot":"--x","hw":false,"trace":false,"enabled":true,"data":"","cond":""}
        db["breakpoints"] = [{
            "address": hex(bp["addr"] - base_addr), # Comment address relative to the base of the module
            "enabled": bp["enabled"], # Whether the breakpoint is enabled
            "type": BPHARDWARE if bp["hw"] else BPNORMAL, # see https://github.com/x64dbg/x64dbg/blob/development/src/dbg/breakpoint.h#L13
            "module": module, # The module that the comment is in
        } for bp in cutter.cmdj("dbj")]
        cutter.message("[x64dbg-cutter]: %d breakpoint(s) exported" % len(db["breakpoints"]))
        
        # r2: {"offset":5368713216,"type":"CCu","name":"[00] -rwx section size 65536 named .textbss"}
        db["comments"] = [{
            "module": module, # The module that the comment is in
            "address": hex(c["offset"] - base_addr), # Comment address relative to the base of the module
            "manual": True, # Whether the comment was created by the user - set to True to show it in the comments window
            "text": c["name"], # Comment text
        } for c in cutter.cmdj("CCj")]
        cutter.message("[x64dbg-cutter]: %d comment(s) exported" % len(db["comments"]))

        with open(filename, "w") as outfile:
            json.dump(db, outfile, indent=1)

    def import_db(self):
        filename = self.file_dialog("Open x64dbg (Uncompressed) JSON database", True)
        if not filename:
            return
    
        cutter.message("[x64dbg-cutter]: Importing database %s" % filename)
    
        with open(filename) as dbdata:
            db = json.load(dbdata)
    
        # We can only import symbols for the main binary currently
        module = os.path.basename(cutter.cmdj("ij")["core"]["file"]).lower()
        base_addr = cutter.cmdj("evj bin.baddr")[0]["value"]
        
        count = 0
        breakpoints = db.get("breakpoints", [])
        for bp in breakpoints:
            try:
                if bp["module"] != module:
                    continue
                address = int(bp["address"], 16) + base_addr
                cutter.cmd("dbs " + str(address))
                # Breakpoints created by dbs are enabled by default
                if not bp["enabled"]:
                    cutter.cmd("dbd " + str(address))
                count += 1
            except:
                cutter.message("[x64dbg-cutter]: " + traceback.format_exc())
        cutter.message("[x64dbg-cutter]: %d/%d breakpoints(s) imported" % (count, len(breakpoints)))
    
        count = 0
        comments = db.get("comments", [])
        for comment in comments:
            try:
                if comment["module"] != module:
                    continue
                address = int(comment["address"], 16) + base_addr
                text = base64.b64encode(comment["text"].encode("utf-8")).decode()
                cutter.cmd("CCu base64:" + text + " @ " + str(address))
                count += 1
            except:
                cutter.message("[x64dbg-cutter]: " + traceback.format_exc())
        cutter.message("[x64dbg-cutter]: %d/%d comment(s) imported" % (count, len(comments)))
        
        cutter.message("[x64dbg-cutter]: Done!")

class x64dbgCutterPlugin(cutter.CutterPlugin):
    name = 'x64dbg-cutter'
    description = 'Import and export x64dbg comments and breakpoints in Cutter'
    version = '1.0'
    author = 'Yossi Zap'

    def __init__(self):
        super(x64dbgCutterPlugin, self).__init__()
        self.ui = None

    def setupPlugin(self):
        pass

    def setupInterface(self, main):
        self.main = main
        self.ui = x64dbgCutter(self, main)
        self.ui.load()

    def terminate(self):
        if self.ui:
            self.ui.unload()

def create_cutter_plugin():
    return x64dbgCutterPlugin()