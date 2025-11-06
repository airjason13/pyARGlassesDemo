import os, json, glob

# PlaylistManager
class PlaylistManager:
    def __init__(self, base_path: str):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)
        self.current_list = None

    def _path(self, name: str) -> str:
        if not name.endswith(".list"):
            name += ".list"
        return os.path.join(self.base_path, name)

    def _load(self, name: str) -> dict:
        with open(self._path(name), "r") as f:
            return json.load(f)

    def _save(self, name: str, data: dict) -> None:
        with open(self._path(name), "w") as f:
            json.dump(data, f, indent=2)

    # === Create Playlist ===
    def create(self, name: str):
        if not name or not name.strip():
            return {"status": "NG", "error": "Invalid playlist name"}
        p = self._path(name)
        if os.path.exists(p):
            return {"status": "NG", "error": "Playlist already exists"}
        self._save(name, {"name": name, "files": []})
        self.current_list = name
        return {"status": "OK", "created": name, "current": self.current_list}

    def select(self, name: str):
        if not name or not name.strip():
            return {"status": "NG", "error": "Invalid playlist name"}
        p = self._path(name)
        if not os.path.exists(p):
            return {"status": "NG", "error": f"Playlist '{name}' not found"}
        self.current_list = name
        return {"status": "OK", "selected": name}

    def get_all(self):
        lists = [
            os.path.basename(f).replace(".list", "")
            for f in glob.glob(os.path.join(self.base_path, "*.list"))
        ]
        if not lists:
            return {"status": "NG", "error": "No playlist found", "playlists": [], "current": None}
        return {"status": "OK", "playlists": lists, "current": self.current_list}

    def add_item(self, filename: str):
        if not self.current_list:
            return {"status": "NG", "error": "No playlist selected"}
        if not filename or not filename.strip():
            return {"status": "NG", "error": "Invalid filename"}
        data = self._load(self.current_list)
        '''
        if filename in data["files"]:
            return {"status": "NG", "error": f"'{filename}' already in playlist '{self.current_list}'"}
        '''
        data["files"].append(filename)
        self._save(self.current_list, data)
        return {"status": "OK", "added": filename, "list": self.current_list}

    def get_current_list(self, name: str | None = None):
        name = name or self.current_list
        if not name:
            return {"status": "NG", "error": "No playlist selected"}
        p = self._path(name)
        if not os.path.exists(p):
            return {"status": "NG", "error": f"Playlist '{name}' not found"}
        data = self._load(name)
        return {"status": "OK", "playlist": name, "files": data.get("files", [])}

    def remove_item(self, filename: str):
        if not self.current_list:
            return {"status": "NG", "error": "No playlist selected"}
        if not filename or not filename.strip():
            return {"status": "NG", "error": "Invalid filename"}
        data = self._load(self.current_list)
        if filename not in data["files"]:
            return {"status": "NG", "error": f"'{filename}' not in playlist '{self.current_list}'"}
        data["files"].remove(filename)
        self._save(self.current_list, data)
        return {"status": "OK", "removed": filename, "list": self.current_list}

    def get_files_in_current_list(self):
        if not self.current_list:
            return {"status": "NG", "error": "No playlist selected"}
        data = self._load(self.current_list)
        return {"status": "OK", "playlist": self.current_list, "files": data.get("files", [])}

    def remove_playlist(self, name: str):
        if not name:
            return {"status": "NG", "error": "No playlist name provided"}

        p = self._path(name)
        if not os.path.exists(p):
            return {"status": "NG", "error": f"Playlist '{name}' not found"}

        try:
            os.remove(p)
            # If it is the currently selected list, clear the current list
            if self.current_list == name:
                self.current_list = None
            return {"status": "OK", "removed": name}
        except Exception as e:
            return {"status": "NG", "error": str(e)}

    def add_item_to_target_playlist(self, playlist_name: str, filename: str):
        if not playlist_name or not playlist_name.strip():
            return {"status": "NG", "error": "Invalid playlist name"}
        if not filename or not filename.strip():
            return {"status": "NG", "error": "Invalid filename"}

        p = self._path(playlist_name)

        try:
            # If the list does not exist, it will be created automatically.
            if not os.path.exists(p):
                self._save(playlist_name, {"name": playlist_name, "files": []})

            # load playlist data
            data = self._load(playlist_name)
            '''
            # Check if the item is duplicated
            if filename in data.get("files", []):
                return {"status": "NG", "error": f"'{filename}' already in playlist '{playlist_name}'"}
            '''
            # AddItem
            data["files"].append(filename)
            self._save(playlist_name, data)
            return {"status": "OK", "playlist": playlist_name, "added": filename}

        except Exception as e:
            return {"status": "NG", "error": str(e)}

    def remove_item_to_target_playlist(self, playlist_name: str, filename: str):
        if not playlist_name or not playlist_name.strip():
            return {"status": "NG", "error": "Invalid playlist name"}
        if not filename or not filename.strip():
            return {"status": "NG", "error": "Invalid filename"}

        p = self._path(playlist_name)
        if not os.path.exists(p):
            return {"status": "NG", "error": f"Playlist '{playlist_name}' not found"}

        try:

            data = self._load(playlist_name)
            files = data.get("files", [])
            if filename not in files:
                return {"status": "NG", "error": f"'{filename}' not in playlist '{playlist_name}'"}

            files.remove(filename)
            self._save(playlist_name, data)
            return {"status": "OK", "playlist": playlist_name, "removed": filename}
        except Exception as e:
            return {"status": "NG", "error": str(e)}
