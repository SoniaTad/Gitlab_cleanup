import requests
from ms_active_directory import ADDomain
from os import getenv
import logging
import re


#getting env variables
Token=getenv('Token')
username=getenv('ADusername')
ps=getenv('ADps')
ADdomain=getenv('ADdomain')
Host=getenv('GitlabHost')
DryRun=bool(getenv('DryRun'))

# local variables
Users_with_NOgroups=[]
Users_with_groups=[]
payload={}
log_file='app.log'
log=logging.basicConfig(filename=log_file, filemode='a', format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%d-%m-%y %H:%M:%S',level=logging.INFO)

#check that the env variable is not empty
if not Token :
    log
    logging.warning('No Token is currently available!')
    exit()
elif not username:
    log
    logging.warning('No AD username is currently available!')
    exit()
elif not ps:
    log
    logging.warning('No AD password is currently available!')
    exit()
elif not ADdomain:
    log
    logging.warning('No AD domain is specified!')
    exit()
elif not Host:
    log
    logging.warning('No Host detected')
elif not DryRun:
    log
    logging.warning('Dry run not specified. Assuming False')
    DryRun = False

headers={'Authorization':Token}

try:
    domain = ADDomain(ADdomain,site='')    # add a specific site if needed for the AD check 
    session = domain.create_session_as_user(username, ps) 
except:
    log
    logging.warning('Wrong password or username')
    exit()

def delete_duplicates(List):
    New_list=[]
    for i in range(len(List)):
        if List[i] not in List[i + 1:]:
            New_list.append(List[i])
    return New_list


# step 1 : getting the total number of pages with 100 users per page
URL="https://{}/api/v4/users?active=true&per_page=100".format(Host)
#print(URL)
response = requests.request("GET", URL, headers=headers, data=payload)

total_pages=response.headers['X-Total-Pages']
log
logging.info('Sending a request to get the total number of pages')

logging.warning('that is the number of pages {total_pages}'.format(total_pages=total_pages))
#print(total_pages)
logging.info('looping through the pages of users')

# step 2: looping through the different pages to get all users 
for x in range(1,(int(total_pages )+1)):

    params = {'page': x}
    link='https://{}/api/v4/users?active=true&per_page=100'.format(Host)
    response = requests.get(link,
            params=params,headers=headers)
    body=response.json()
    
    # step 3 : check if each user of each json page has an AD account , appending to 2 different lists accordingly 
    for user in body:
        noreply = re.findall("@(live.)?companyName.uk$", user['email'])    #change the email ending if looking for something specific 
        if not noreply :
            pass
        else:
            #method takes 3 parameters (type_of_attr,value_of_attr,attr_to_look_up)
            u = session.find_users_by_attribute('mail',user['email'],['mail'])
            if (len(u) != 0):
                pass
                
            else:
                
                #step 4 : check if the users with no AD are part of a group or contributed to someone else's project 
                ID=user['id']
                id=str(ID)
                url='https://{}/api/v4/users/{}/memberships'.format(Host,id)
                
                RESPONSE = requests.get(url,headers=headers)
                result=RESPONSE.json()
    
                # Namespace represents  a group and access level =50 indicates that the user is the owner of a specific project/group 
                for project in result:
                    if ((project['source_type']=='Namespace') or (project['source_type']=='Project' and project['access_level']!=50 ) ):
                        
                        Users_with_groups.append(user)
                        break
                    elif (project['source_type']=='Project' and project['access_level']==50):
                        project_id=project['source_id']
                        project_id=str(project_id)
                        URL="https://{}/api/v4/projects/{}/members".format(Host,project_id)
                        response = requests.request("GET", URL, headers=headers, data=payload)
                        members=response.json()
                        if (len(members)>1):
                            #this user needs to be blocked 
                            Users_with_groups.append(user)
                            break
                        else:
                            if re.findall("@companyName.uk$", user['email']):
                                Url='https://{}/api/v4/users/{}/projects'.format(Host,id)
                                API_response = requests.get(Url, headers=headers)   
                                prj=API_response.json()
                                for p in prj:
                                    if (p['visibility']!='private'):
                                        Users_with_groups.append(user)
                                    else:
                                        Users_with_NOgroups.append(user)
                            else:
                                # while they are a project owner no other member exists therefore can safely be deleted
                                Users_with_NOgroups.append(user)   
                        
                    else:
                        Users_with_NOgroups.append(user)

log
logging.info('Successfully separated the users with groups from the ones without')
logging.info('Deleting duplicates from lists')
# step 5: deleting duplicates from the lists before progressing to the next step 
if (len(Users_with_groups) == 0) :
    #print('no users with a group')
    Usertoblock=[]
else:
    # remove duplicates from it 
    Usertoblock=delete_duplicates(Users_with_groups)
    #print(Usertoblock)

if (len(Users_with_NOgroups)==0):
    #print('no user without a group')
    Usertodelete=[]
else:
    Usertodelete=delete_duplicates(Users_with_NOgroups)
    
#print(len(Usertoblock))
#print(len(Usertodelete))


log
logging.info('last check before deletion')
# step 6 : check if users from list to delete are in the block list if so remove them from the delete lsit 

Newdelete = [i for i in Usertodelete if i not in Usertoblock]
  

#print(len(Newdelete))
log
logging.info('Users are being either blocked or deleted')

# step 7: block and delete users 
if (len(Usertoblock)!=0):
    for User in Usertoblock:
        id=str(User['id'])
        un=str(User['email'])
        url='https://{}/api/v4/users/{}/block'.format(Host,id)
        
        log
        logging.warning('Username of the user to block {un}'.format(un=un))
        if DryRun:
            log
            logging.info('Dry Run mode, no action will be taken')
        else:
            RESPONSE = requests.post(url,headers=headers)
            result=RESPONSE.json()
            #print(result)
else:
    log
    logging.info('Everyone has already been blocked')
    
    pass

if (len(Newdelete)!=0):
    for User in Newdelete:
        id=str(User['id'])
        un=str(User['email'])
        url='https://{}/api/v4/users/{}'.format(Host,id)
        
        #print(url)
        log
        logging.warning('ID of user to delete {un}'.format(un=un))
        if DryRun:
            log
            logging.info('Dry Run mode, no action will be taken')
        else:
            RESPONSE = requests.delete(url,headers=headers)
            #print(RESPONSE)
            log
            logging.info('check if the response returns a 204 status if so the deletion was a success')
            logging.info('the response:{RESPONSE}'.format(RESPONSE=RESPONSE))
       
else:
    log
    logging.info('Everyone has already been deleted')
    pass
num_block=len(Usertoblock)
num_delete=len(Newdelete)
log 
logging.info('The number of users to block is {num_block}'.format(num_block=num_block))
logging.info('The number of users to delete is {num_delete}'.format(num_delete=num_delete))
logging.info('End of the script')
