# Copyright © 2020  Gaute Hope <eg@gaute.vetsj.com>
#
# This file is part of Lieer.
#
# Lieer is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import json
import tempfile


class ResumePull:
    lastId = None
    version = None
    VERSION = 1

    meta_fetched = None

    @staticmethod
    def load(resume_file):
        """
        Construct from existing resume
        """
        with open(resume_file) as fd:
            j = json.load(fd)

            version = j["version"]
            if version != ResumePull.VERSION:
                print(
                    "error: mismatching version in resume file: %d != %d"
                    % (version, ResumePull.VERSION)
                )
                raise ValueError()

            lastId = j["lastId"]
            meta_fetched = j["meta_fetched"]

        r = ResumePull(resume_file, lastId)
        r.meta_fetched = meta_fetched

        return r

    @staticmethod
    def new(resume_file, lastId):
        r = ResumePull(resume_file, lastId)
        r.meta_fetched = []
        r.save()

        return r

    def __init__(self, resume_file, lastId):
        self.resume_file = resume_file
        self.lastId = lastId
        self.meta_fetched = []

    def update(self, fetched):
        """
        fetched: new messages with metadata fetched
        """
        self.meta_fetched.extend(fetched)
        self.meta_fetched = list(set(self.meta_fetched))
        self.save()

    def save(self):
        j = {
            "version": self.VERSION,
            "lastId": self.lastId,
            "meta_fetched": self.meta_fetched,
        }

        with tempfile.NamedTemporaryFile(
            mode="w+", dir=os.path.dirname(self.resume_file), delete=False
        ) as fd:
            json.dump(j, fd)

            if os.path.exists(self.resume_file):
                os.rename(self.resume_file, self.resume_file + ".bak")

            os.rename(fd.name, self.resume_file)

    def delete(self):
        os.unlink(self.resume_file)
