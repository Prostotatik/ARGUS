import sys
sys.path.insert(0, r"E:/Projects/Averis x Monash/backend")
from sdoc import normalize as nz
def t(kind, a, b, expect):
    if kind=="name": r=nz.names_equal(a,b).match
    elif kind=="port": r=nz.ports_equal(a,b).match
    elif kind=="wt": r=nz.weights_equal(nz.parse_weight_kg(a), nz.parse_weight_kg(b)).match
    elif kind=="cnt": r=(nz.parse_container_count(a).count==nz.parse_container_count(b).count and nz.parse_container_count(a).count is not None)
    flag = "ok " if r==expect else "BAD"
    if r!=expect: print(flag, kind, repr(a), "vs", repr(b), "got match=",r, "expected", expect)
    return r==expect
res=[]
# EQUIVALENT (expect True)
names = [
 ("APRIL FAR EAST (M) SDN BHD","APRIL FAR EAST (M) SDN. BHD."),
 ("APRIL FAR EAST (M) SDN BHD","April Far East (M) Sdn Bhd"),
 ("APRIL FAR EAST (M) SDN BHD","APRIL FAR EAST (M) S/B"),
 ("APRIL FAR EAST (M) SDN BHD","APRIL FAR EAST (MALAYSIA) SDN BHD"),
 ("KTP CO., LTD","KTP CO LTD"),
 ("KTP CO., LTD","KTP COMPANY LIMITED"),
 ("KTP CO., LTD","KTP CO., LTD."),
 ("VITAL SOLUTIONS PTE. LTD.","VITAL SOLUTIONS PTE LTD"),
 ("VITAL SOLUTIONS PTE. LTD.","VITAL SOLUTIONS (S) PTE LTD"),
 ("AL GURG STATIONERY LLC","AL GURG STATIONERY L.L.C."),
 ("AL GURG STATIONERY LLC","AL-GURG STATIONERY LLC"),
 ("AL GURG STATIONERY LLC","AL GURG STATIONERY LLC, DUBAI"),
 ("ROXCEL TRADING GMBH","ROXCEL TRADING GMBH & CO. KG"),
 ("PT INDAH KIAT PULP & PAPER TBK","PT. INDAH KIAT PULP AND PAPER TBK"),
 ("PT INDAH KIAT PULP & PAPER TBK","INDAH KIAT PULP & PAPER TBK"),
 ("EAST BRIGHT FZ-LLC","EAST BRIGHT FZ LLC"),
 ("EAST BRIGHT FZ-LLC","EAST BRIGHT FZLLC"),
 ("ACME TRADING INC.","ACME TRADING INCORPORATED"),
 ("ACME TRADING LTD","ACME TRADING LIMITED."),
 ("NAGAPPA EXPORTS","NAGAPPA EXPORTS "),
 ("Müller GmbH","MULLER GMBH"),
 ("ACME (S) PTE LTD","ACME SINGAPORE PTE LTD"),
]
for a,b in names: res.append(t("name",a,b,True))
ports = [
 ("SINGAPORE (SGSIN)","SINGAPORE"),
 ("SINGAPORE (SGSIN)","SINGAPORE, SINGAPORE"),
 ("SINGAPORE (SGSIN)","SINGAPORE SGSIN"),
 ("SINGAPORE (SGSIN)","SGSIN"),
 ("SINGAPORE (SGSIN)","PORT OF SINGAPORE"),
 ("SINGAPORE (SGSIN)","Singapore Port"),
 ("SINGAPORE (SGSIN)","SINGAPORE, SG"),
 ("SINGAPORE (SGSIN)","Singapore (PSA Terminal)"),
 ("PORT KLANG (WESTPORT), MALAYSIA (MYPKG)","PORT KLANG, MALAYSIA"),
 ("PORT KLANG, MALAYSIA","KLANG"),
 ("PORT KLANG, MALAYSIA","PORT KLANG (MYPKG)"),
 ("PORT KLANG, MALAYSIA","PORT KLANG MALAYSIA"),
 ("PORT KLANG, MALAYSIA","Port Klang - Malaysia"),
 ("HOCHIMINH CITY, VIETNAM (VNSGN)","HO CHI MINH CITY, VIET NAM"),
 ("HOCHIMINH CITY, VIETNAM (VNSGN)","HCMC, VIETNAM"),
 ("HOCHIMINH CITY, VIETNAM (VNSGN)","CAT LAI, VIETNAM"),
 ("ROTTERDAM, NETHERLANDS","ROTTERDAM"),
 ("ROTTERDAM, NETHERLANDS","ROTTERDAM, THE NETHERLANDS"),
 ("ROTTERDAM, NETHERLANDS","ROTTERDAM, NL"),
 ("ROTTERDAM (NLRTM)","ROTTERDAM, NETHERLANDS"),
 ("HAMBURG, GERMANY","HAMBURG"),
 ("COLOMBO, SRI LANKA","COLOMBO"),
 ("BANDAR ABBAS, IRAN","BANDAR ABBAS"),
 ("UMM QASR, IRAQ","UMM QASR"),
 ("CARTAGENA, COLOMBIA","CARTAGENA"),
 ("BUENOS AIRES, ARGENTINA","BUENOS AIRES"),
 ("GUAYAQUIL, ECUADOR","GUAYAQUIL"),
 ("DAR ES SALAAM, TANZANIA","DAR ES SALAAM"),
 ("LAEM CHABANG, THAILAND","LAEM CHABANG"),
 ("KAOHSIUNG, TAIWAN","KAOHSIUNG"),
 ("XIAMEN, CHINA","XIAMEN"),
 ("DJIBOUTI","DJIBOUTI, DJIBOUTI"),
 ("BUSAN, SOUTH KOREA","BUSAN, KOREA"),
 ("BUSAN, SOUTH KOREA","PUSAN, S. KOREA"),
 ("JEBEL ALI, UAE","JEBEL ALI, UNITED ARAB EMIRATES"),
 ("JEBEL ALI, UAE","JEBEL ALI PORT"),
 ("LOS ANGELES, US","LOS ANGELES, CA, USA"),
 ("NEW YORK, US","NEW YORK, NY"),
 ("PORT KELANG","PORT KLANG"),
 ("TANJUNG PELEPAS, MALAYSIA","TANJUNG PELEPAS (PTP), MALAYSIA"),
 ("TANJUNG PELEPAS, MALAYSIA","PTP"),
]
for a,b in ports: res.append(t("port",a,b,True))
wts=[("22,000 KG","22000 KGS"),("22,000 KG","22,000.00 KG"),("22,000 KG","22.000 KG"),("22,000 KG","22 MT"),("22,000 KG","22.000 MT"),("22,000 KG","22.0 MT"),
 ("22,000 KG","22000KG"),("22,000 KG","KGS 22,000"),("22,000 KG","22 000 KG"),("22,000 KG","22,000 Kgs."),("22,000 KG","48,501 LBS"),("22,000 KG","22000 kg (approx.)"),
 ("22,000 KG","22,000.000 KG"),("22,000.50 KG","22,000.5 KG"),("22,000 KG","22.00 TONS"),("22,000 KG","22,000 K.G."),("22,000 KG","22'000 KG"),
 ("131,058 KG","131058"),("131,058 KG","131.058 KG"),("22,000 KG","22000.0"),("22,000 KG","22,000 KGM"),("22,000 KG","22,000 KILOGRAMS"),("22,000 KG","22.0 M/T"),("22,000 KG","22 MTON"),("22,000 KG", "22,000 KG GROSS")]
for a,b in wts: res.append(t("wt",a,b,True))
cnts=[("6 x 40'HC","6 X 40HC"),("6 x 40'HC","6 x 40 HC"),("6 x 40'HC","SIX (6) x 40'HC"),("6 x 40'HC","6"),("6 x 40'HC","6 CONTAINERS"),("6 x 40'HC","6x40'HC"),("6 x 40'HC","6 × 40'HC"),("6 x 40'HC","06"),
 ("6 x 40'HC","6 (40' HC)"),("6 x 40'HC","40'HC x 6"),("6 x 40'HC","6 x 40' HIGH CUBE"),("6 x 40'HC","6 CNTR"),("6 x 40'HC","6 x FCL 40HC"),("6 x 40'HC","6 X 40FT HC"),("6 x 40'HC","6 CONTAINER(S) 40HC"),("6 x 40'HC","6 UNITS"),("6 x 40'HC","6 x 40-HC"),("6 x 40'HC", "6 x 40' HC (FCL/FCL)"),("2 x 40'HC","2 x 40'HC, 2 x 40'HC")]
for a,b in cnts: res.append(t("cnt",a,b,True))
# NOT EQUIVALENT (expect False) - real defects must be caught
neg_names=[("EAST BRIGHT FZ-LLC","EAST BRIGHT FZE"),("ACME TRADING LTD","ACME TRADING PTE LTD"),("APRIL FINE PAPER TRADING","APRIL FINE PAPER TRADING (MIDDLE EAST) FZE"),("KTP CO., LTD","KTP CO., LTD 2"),
 ("ACME TRADING LTD","ACME TRADING LTDA"),("ACME EXPORTS LTD","ACME IMPORTS LTD"),("SAFQA LIMITED","SAFQA"),("ROXCEL TRADING GMBH","ROXCEL TRADING GMBH & CO KG"),("NAGAPPA EXPORTS","NAGAPA EXPORTS"),("TOPKOPY MIDDLE EAST FZE","TOPKOPY MIDDLE EAST FZC"),("3S PAPER PRODUCTS SDN BHD","3S PAPER PRODUCT SDN BHD"),("ACME TRADING LTD","ACME TRADING")]
for a,b in neg_names: res.append(t("name",a,b,False))
neg_ports=[("SINGAPORE","SINGAPORE (JURONG)"),("PORT KLANG","PORT KLANG (NORTHPORT)"),("NHAVA SHEVA","MUNDRA"),("BUSAN","BUSAN NEW PORT"),("NANTONG","NANJING"),("SINGAPORE (SGSIN)","SINGAPORE (SGSIP)"),("JEBEL ALI","JEBEL ALI FZ")]
for a,b in neg_ports: res.append(t("port",a,b,False))
neg_w=[("22,000 KG","22,001 KG"),("22,000 KG","22,000.9 KG"),("22,000 KG","22.001 MT"),("22,000 KG","22,000 LBS"),("131,058 KG","131,085 KG"),("22,000 KG","2,200 KG"),("22,000 KG","220,000 KG"), ("22,000 KG","22,000 MT")]
for a,b in neg_w: res.append(t("wt",a,b,False))
neg_c=[("6 x 40'HC","5 x 40'HC"),("6 x 40'HC","6 x 20'GP"),("2 x 40'HC","4 x 40'HC"),("6 x 40'HC","60")]
for a,b in neg_c[:3]+[neg_c[3]]: res.append(t("cnt",a,b,False))
print(sum(res),"/",len(res),"as expected")
