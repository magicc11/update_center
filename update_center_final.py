from bs4 import BeautifulSoup as soup
import datetime
import argparse
import os
import requests
import time
import logging
import configparser
from artifactory import ArtifactoryPath
import base64
from decimal import Decimal as D


# Configuration Section

# Infineon Proxies to access the plugins url
proxies = {
    'http': 'http://proxy.vih.infineon.com:80',
    'https': 'http://proxy.vih.infineon.com:80',
    }

# Main Url to fetch plugins
url='http://updates.jenkins-ci.org/'

# Config file having details of supported jenkins version and API key for Artifactory authentication
config_file='updc.ini'

# Creating parser for config file
config = configparser.ConfigParser()
config.read(config_file)


#arpath = ArtifactoryPath("http://localhost:8081/artifactory/jenkins-integration/2.222")

# Functions Section


def check_args():
    """Parses the command line arguments and returns a argument object"""
    parser = argparse.ArgumentParser(description='Parse command line arguments')
    parser.add_argument('updcpath', action = 'store', help = 'Path to local clone of updc')
    parser.add_argument('--specific_version', action='store', help='Jenkins version')
    parser.add_argument('afrepopath', action='store', help='Artifactory path to the plugins subfolder')
    parser.add_argument('--upload_via_script',action='store_true', help='If mentioned, uploads the plugins to artifactory.')
    arg = parser.parse_args()
    return arg


def download_plugin(version_url,path):
    """Downloads the plugins in the specified path """
    print("current dir above exl %s" % os.getcwd())
    with open("exception_list.txt", "r") as el:
        read_exclusion_list = el.readlines()
        exclusion_list = [x.replace('\n', '') for x in read_exclusion_list]
        print("Fetching Exclusion List")
        logging.info("Exclusion list: %s" %exclusion_list)

    while 1:
        try:
            #prod#resp = requests.get(version_url,proxies=proxies)
            resp = requests.get(version_url)
        except:
            logging.exception("Exception occurred : Unable to connect to plugins url %s" %version_url)
            break
        else:
            break
    print("Downloading Plugins...")
    page_soup = soup(resp.text, "html.parser")
    count=0
    not_downloaded=[]
    for i in page_soup.find_all('a', href=True)[:-1]:
        if count > 13:
            break

        plugin_full_name=str(i['href'])
        plugin_name=plugin_full_name.split(".")[0]
        if plugin_name in exclusion_list:
            logging.info("Skipping the download as plugin %s is in Exclusion List" %plugin_name)
            continue
        plugin_url = str(version_url + plugin_full_name)
        os.chdir(path)
        path=os.getcwd()
        count = count + 1
        with open(plugin_full_name, 'wb') as file:
            try:
                #prod#resp = requests.get(plugin_url,proxies=proxies,timeout=(2, 60)
                resp = requests.get(plugin_url,timeout=(2, 60))
                file.write(resp.content)
            except:
                print("inside exception for %s" %plugin_name)
                not_downloaded.append(plugin_full_name)
                print("list Not downloaded %s:" %not_downloaded)
                pass
    if not_downloaded:
        print("inside not downloaded")
        print(os.getcwd())
        remove_plugins(not_downloaded)

def remove_plugins(remove_list):
    for i in remove_list:
        print("Removing corrupt plugin:  %s" %i )
        os.remove(i)

def upload_artifactory(arpath, p_path):
    """Uploads the downloaded plugins to Artifactory repository"""
    plugin_list = os.listdir(p_path)
    os.chdir(str(p_path))
    logging.info("Uploading Plugins to Artifactory")
    for i in plugin_list:
        print("Uploading plugin:  %s " %i)
        try:
            arpath.deploy_file(i)
        except ConnectionRefusedError:
            print("Unable to connect to Artifactory")

def setting_version_specific_details(afpath, version):
    """Returns Artifactory path and  Jenkins plugin url for specific version"""
    user=list(config['APIKEY'].keys())[0]
    apikey=config['APIKEY'][user]
    apath=ArtifactoryPath(afpath+version,auth=(user, apikey))
    print("apath inside settings %s" %apath)
    return apath


def checking_config(ver):
    """Checks if the the jenkins version passed in the command line is supported or not"""
    supported_ver=list(config['VERSION'].values())
    if ver not in supported_ver:
        print("The Jenkins version %s is not supported exiting !, %version")
        exit(1)


def urls_check(version,b_url):
    url_link=False
    x = D(version)
    while not url_link:
        url = b_url + str(x) + "/latest"
        print("new url is %s" % url)
        r=requests.get(url)
        if r.status_code == 200:
            print("Connected to URL %s" %url)
            url_link=True
            return url
        mille = D('.001')
        x -= mille

def main():
    arg = check_args()
    path = arg.updcpath
    s_version = arg.specific_version
    afpath=arg.afrepopath
    cpath=os.getcwd()
    print("current wdir at start %s" %cpath)
    log_path = os.path.join(path,"..")
    log_folder_path = os.path.join(log_path,"log")
    if not os.path.exists(log_folder_path):
        os.mkdir(log_folder_path)
    log_file_name = "updatecenter_log_"+datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")+".log"
    logging.basicConfig(filename=os.path.join(log_folder_path,log_file_name),format='%(asctime)s %(levelname)s %(message)s',level=logging.INFO)

    supported_ver = list(config['VERSION'].values())
    print(supported_ver)
    if s_version:
        supported_ver=[s_version]
        print("supported ver inside specific %s" %supported_ver)
        checking_config(s_version)
        logging.info("Creating update center for specific version")
    for version in supported_ver:
        plugin_path=path+version
        afpath = arg.afrepopath
        logging.info("Creating Update Center for Jenkins Version %s", version)
        print("Creating Update Center for Jenkins Version %s" %version)
        logging.info("Plugin Path is: %s" %plugin_path)
        if (not (os.path.exists(plugin_path))):
            os.makedirs(plugin_path)
        logging.info("Update center path : " + path)
        #version_url = 'https://updates.jenkins.io/' + version + "/latest/"
        print("version is %s" %version)
        print(("afpath is %s" %afpath))
        afpath=setting_version_specific_details(afpath, version)
        logging.info("Artifactory path : %s" %afpath)
        path2=os.getcwd()
        version_url=urls_check(version,url)
        os.chdir(cpath)
        download_plugin(version_url,plugin_path)
        os.chdir(str(path2))
        if arg.upload_via_script:
            logging.info("Uploading Plugins to Artifactory.")
            print("afpath above upload function is : %s" %afpath)
            upload_artifactory(afpath, plugin_path)

    print("Completed Update-center execution ")


if __name__ == '__main__':
    main()