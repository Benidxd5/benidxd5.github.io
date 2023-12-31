import os
import time
import re
import yaml

import requests
import sqlite3
from sqlite3 import Error
from urllib.parse import quote


db_path = ".tmp/source/Public/index.db"


def get_id(con, cursor, table, field, value, force_new=False):
    print("getid")
    cursor.execute('SELECT rowid FROM {} WHERE {} = "{}";'.format(table, field, value))
    row = cursor.fetchall()

    if len(row) == 0 or force_new:
        cursor.execute('SELECT MAX(rowid) + 1 FROM {}'.format(table))
        id_ = cursor.fetchall()[0][0]
        if not id_:
            id_ = 1

        cursor.execute(
            'INSERT INTO {} (rowid, {}) VALUES (?,?)'.format(table, field),
            (id_, value)
        )
        con.commit()

        return id_
    
    # print("row info")

    # print(value)
    # print(row)
    # print(occNum)
    # if(len(row)>1):
    #     return row[occNum][0]

    return row[0][0]


def normalize(name):
    return name.replace(' ', '').lower()

packageVersions = {}

def register_manifest(con, cursor, data, pathParts, manifest, manifestFilename):
    # IDS
    id_ = get_id(con, cursor, 'ids', 'id', data['PackageIdentifier'])

    # NAMES
    if not 'PackageName' in data:
        data['PackageName'] = data['PackageIdentifier'].split('.')[-1]

    name = get_id(con, cursor, 'names', 'name', data['PackageName'])

    # MONIKERS
    if not 'Moniker' in data:
        data['Moniker'] = data['PackageName'].lower()

    moniker = get_id(con, cursor, 'monikers', 'moniker', data['Moniker'])

    # VERSION
    version = get_id(con, cursor, 'versions', 'version', data['PackageVersion'])

    # PATHPARTS
    parent_pathpart = 1

    path = ""
    for part in pathParts[1:]:
        pathpart = get_id(con, cursor, 'pathparts', 'pathpart', part, True)
        cursor.execute('UPDATE pathparts SET parent={} WHERE rowid={};'.format(parent_pathpart, pathpart))
        parent_pathpart = pathpart
        path+=part+"/"
    
    path+=manifestFilename
    pathpart = get_id(con, cursor, 'pathparts', 'pathpart', manifestFilename, True)
    cursor.execute('UPDATE pathparts SET parent={} WHERE rowid={};'.format(parent_pathpart, pathpart))

    con.commit()

    # MANIFEST ##pathpart --> 1
    cursor.execute(
        'INSERT INTO manifest (rowid, id, name, moniker, version, channel, pathpart) VALUES (?,?,?,?,?,?,?)',
        (manifest, id_, name, moniker, version, 1, pathpart)
    )
    con.commit()

    ##push to strapi

    # The API endpoint to communicate with
    url_post = os.environ.get("API_URL")+"approved-packages"

    print(url_post)

    print("VERSIONS")
    print(packageVersions)

    token = os.environ.get("API_TOKEN")

    if(data['PackageIdentifier'] in packageVersions):
        packageVersions[data['PackageIdentifier']][str(data['PackageVersion'])] = path

    else:
        packageVersions[data['PackageIdentifier']] = {str(data['PackageVersion']):path}
        
    #fetch package to get id
    parsedIdentifier = quote(data["PackageIdentifier"])
    fetchResponse = requests.get(url=(url_post+'?filters[identifier][$eq]='+parsedIdentifier), headers={"Authorization": token, "Content-Type": "application/json"})
    if(not fetchResponse):
        return
    
    fetchResponseJson = fetchResponse.json()
    print(fetchResponseJson)
    if(len(fetchResponseJson["data"])>0):
        print("UPDATE: " +data["PackageName"])
        pkgID = fetchResponseJson["data"][0]["id"]
        updated_package = {
            "name": data['PackageName'],
            "identifier": data["PackageIdentifier"],
            "description": data["Description"] if "Description" in data else " ",
            "versions": packageVersions[data['PackageIdentifier']],
            "path": path
        }
        payload = {
            "data": updated_package
        }
        requests.put(url=(url_post+"/"+str(pkgID)), json=payload, headers={"Authorization": token, "Content-Type": "application/json"})
    
    else:
        print("POST: " +data["PackageName"])
        new_package = {
            "name": data['PackageName'],
            "identifier": data["PackageIdentifier"],
            "description": data["Description"] if "Description" in data else " ",
            "versions": packageVersions[data['PackageIdentifier']],
            "path": path
        }
        payload = {
            "data": new_package
        }
        post_response = requests.post(url=url_post, json=payload, headers={"Authorization": token, "Content-Type": "application/json"})
        post_response_json = post_response.json()
        print(post_response_json)



    # NORM_NAMES
    norm_name = get_id(con, cursor, 'norm_names', 'norm_name', normalize(data['PackageName']))
    cursor.execute(
        'INSERT INTO norm_names_map (manifest, norm_name) VALUES (?,?)',
        (manifest, norm_name)
    )
    con.commit()

    # NORM_PUBLISHERS
    if not 'Publisher' in data:
        data['Publisher'] = data['PackageIdentifier'].split('.')[0]
    norm_publisher = get_id(con, cursor, 'norm_publishers', 'norm_publisher', normalize(data['Publisher']))
    cursor.execute(
        'INSERT INTO norm_publishers_map (manifest, norm_publisher) VALUES (?,?)',
        (manifest, norm_publisher)
    )
    con.commit()

    # TAGS
    if 'Tags' in data:
        for _tag in data['Tags']:
            tag = get_id(con, cursor, 'tags', 'tag', _tag)
            cursor.execute('INSERT INTO tags_map (manifest, tag) VALUES (?,?)', (manifest, tag))
            con.commit()

    # COMMANDS
    if 'Commands' in data:
        for _command in data['Commands']:
            command = get_id(con, cursor, 'commands', 'command', _command)
            cursor.execute(
                'INSERT INTO commands_map (manifest, command) VALUES (?,?)',
                (manifest, command)
            )
            con.commit()

    # PFNS
    if 'Installers' in data:
        if 'PackageFamilyName' in data['Installers'][0]:
            pfn = get_id(con, cursor, 'pfns', 'pfn', data['Installers'][0]['PackageFamilyName'])
            cursor.execute('INSERT INTO pfns_map (manifest, pfn) VALUES (?,?)', (manifest, pfn))
            con.commit()

        # PRODUCTCODES
        if 'ProductCode' in data['Installers'][0]:
            productcode = get_id(
                con, cursor, 'productcodes', 'productcode',
                data['Installers'][0]['ProductCode']
            )
            cursor.execute(
                'INSERT INTO productcodes_map (manifest, productcode) VALUES (?,?)',
                (manifest, productcode)
            )
            con.commit()


def create_catalog(con):
    cursor = con.cursor()

    # CREATE SQLITE DATABASE
    manifest = 1

    cursor.execute(
        'INSERT INTO pathparts (rowid,pathpart) VALUES (?,?)',
        (1, 'manifests')
    )
    con.commit()

    cursor.execute(
        'UPDATE metadata SET value=? WHERE name=?;', 
        (int(time.time()), 'lastwritetime')
    )
    con.commit()
    print("Current")
    for (root,_,files) in os.walk('./manifests'):
        if re.match('.*(?:[0-9]+\.?){2,3}\.[0-9]+$', root):
            pathParts = root.split(os.path.sep)
            print(pathParts)
            packageName = ".".join(pathParts[2:-1])
            manifestFilename = ""
            packageData = {}
            print("Files:")
            print(files)
            for file in files:
                if file.endswith("def.yaml"):

                    with open(os.path.join(root, file), 'r', encoding='utf-8') as stream:
                        try:
                            data = yaml.load(stream, Loader=yaml.Loader)
                            #data = yaml.safe_load(stream)
                            print('processing', data['PackageIdentifier'], data['PackageVersion'])
                        except yaml.YAMLError as exc:
                            print(exc)

                        packageData = data
                        manifestFilename = file
                            
            register_manifest(con, cursor, packageData, pathParts, manifest, manifestFilename)

            manifest += 1

if __name__ == '__main__':
    if os.path.exists(db_path):
        os.remove(db_path)
    else:
        os.makedirs(os.path.dirname(db_path))
    con = None
    try:
        con = sqlite3.connect(db_path)

        sql_file = open("index.db.sql")
        sql_as_string = sql_file.read()

        cur = con.cursor()
        cur.executescript(sql_as_string)
        con.commit()

        create_catalog(con)
    except Error as e:
        print(e)
    finally:
        if con:
            con.close()