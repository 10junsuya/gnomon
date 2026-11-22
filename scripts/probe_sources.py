"""출처 접속 확인(한 번씩). 이번: 국가 프로젝트 사진 1280px 주소가 실제로 열리는지 확인, 화면 점검용으로 잠깐 받아 둠 (대표 요청 2026-11-22). 결과 → data/probe.json"""
import base64, json, time, urllib.request
from pathlib import Path
UA = {"User-Agent": "GnomonApp/1.0 (https://github.com/10junsuya/gnomon; contact via GitHub issues) python-urllib"}
U = [
 "https://upload.wikimedia.org/wikipedia/commons/thumb/5/57/Data_centers_in_Ashburn.jpg/1280px-Data_centers_in_Ashburn.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ad/President_Donald_Trump_signs_Executive_Orders_at_the_White_House_AI_Summit_at_Andrew_W._Mellon_Auditorium_in_Washington_%2854677035188%29.jpg/1280px-President_Donald_Trump_signs_Executive_Orders_at_the_White_House_AI_Summit_at_Andrew_W._Mellon_Auditorium_in_Washington_%2854677035188%29.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f8/Frontier_supercomputer_%2852291130197%29.jpg/1280px-Frontier_supercomputer_%2852291130197%29.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/6/69/Gas_centrifuge_cascade.jpg/1280px-Gas_centrifuge_cascade.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e8/President_Joe_Biden_announces_CHIPS_and_Science_Act_grants_to_Intel_to_expand_U.S._semiconductor_production_on_March_20%2C_2024%2C_at_the_Intel_Ocotillo_Campus_in_Chandler%2C_Arizona.jpg/1280px-thumbnail.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b3/Datacenter_Server_Racks_%2822370909788%29.jpg/1280px-Datacenter_Server_Racks_%2822370909788%29.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/4/42/Donald_Trump_state_visit_to_Saudi_Arabia%2C_2025-05-13_P20250513DT-0251.jpg/1280px-Donald_Trump_state_visit_to_Saudi_Arabia%2C_2025-05-13_P20250513DT-0251.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/7/74/2019-08-11_Narvik_08.jpg/1280px-2019-08-11_Narvik_08.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/9/98/Cern_datacenter.jpg/1280px-Cern_datacenter.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/JUPITER_racks_with_logos_of_supporters_and_partners._Copyright-_Forschungszentrum_J%C3%BClich_-_Sascha_Kreklau.jpg/1280px-JUPITER_racks_with_logos_of_supporters_and_partners._Copyright-_Forschungszentrum_J%C3%BClich_-_Sascha_Kreklau.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/4/45/Nvidia_DGX-B200-HGX.jpg/1280px-Nvidia_DGX-B200-HGX.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Google_Data_Center%2C_Council_Bluffs_Iowa_%2849062863796%29.jpg/1280px-Google_Data_Center%2C_Council_Bluffs_Iowa_%2849062863796%29.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/Frontier_Supercomputer_%283%29.jpg/1280px-Frontier_Supercomputer_%283%29.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8b/KDB_HQ.jpg/1280px-KDB_HQ.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/9/94/231105-1_TSMC_Fab_21_construction.jpg/1280px-231105-1_TSMC_Fab_21_construction.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/5/50/TSMC_Fab_18_and_fields_May_2025.jpg/1280px-TSMC_Fab_18_and_fields_May_2025.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0b/Intel_Ohio_One_%282024-02-11-04-16-53_UMBRA-06%29.tiff/lossy-page1-1280px-Intel_Ohio_One_%282024-02-11-04-16-53_UMBRA-06%29.tiff.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f0/KIOXIA_Iwate_Kitakami_Site.jpg/1280px-KIOXIA_Iwate_Kitakami_Site.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/2/21/SK_Hynix_SOCAMM_module_Computex_2025.jpg/1280px-SK_Hynix_SOCAMM_module_Computex_2025.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/5/59/Rapidus_factory_under_construction.jpg/1280px-Rapidus_factory_under_construction.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/0/06/JASM_Kumamoto_2024_03.jpg/1280px-JASM_Kumamoto_2024_03.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e7/TSMC_fabs_in_Hsinchu_01.jpg/1280px-TSMC_fabs_in_Hsinchu_01.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Artemis_II_Launch_%28NHQ202604010307%29.jpg/1280px-Artemis_II_Launch_%28NHQ202604010307%29.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Blue_Ghost_M1_on_the_Moon.png/1280px-Blue_Ghost_M1_on_the_Moon.png.png",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9d/FTG-15_Flight_Test_%284108842%29.jpeg/1280px-FTG-15_Flight_Test_%284108842%29.jpeg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/6/61/Vandenberg_launches_SpaceX_Falcon_9_%28181007-F-XJ735-034%29.jpg/1280px-Vandenberg_launches_SpaceX_Falcon_9_%28181007-F-XJ735-034%29.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/5/59/The_station_pictured_from_the_SpaceX_Crew_Dragon_5.jpg/1280px-The_station_pictured_from_the_SpaceX_Crew_Dragon_5.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/7/79/Iss072e316172_%28Oct_23%2C_2024%29_---_The_International_Space_Station_is_pictured_from_the_SpaceX_Dragon_crew_spacecraft_by_a_SpaceX_Crew-8_member_shortly_after_undocking_from_the_Harmony_module%27s_space-facing_port_%28cropped%29.jpg/1280px-thumbnail.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/KSLV-II_Nuri_and_the_launchpad_01.jpg/1280px-KSLV-II_Nuri_and_the_launchpad_01.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/d/df/NISAR_Encapsulated_in_Payload_Fairing_at_ISRO_Launch_Site_%28PIA26611%29.jpg/1280px-NISAR_Encapsulated_in_Payload_Fairing_at_ISRO_Launch_Site_%28PIA26611%29.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2c/Construction_at_Vogtle_Unit_3_-_August_2013_%2814676545094%29.jpg/1280px-Construction_at_Vogtle_Unit_3_-_August_2013_%2814676545094%29.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b9/Three_Mile_Island_%28color%29.jpg/1280px-Three_Mile_Island_%28color%29.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/5/57/The_Advanced_Test_Reactor_at_Idaho_National_Laboratory_%2814676550274%29.jpg/1280px-The_Advanced_Test_Reactor_at_Idaho_National_Laboratory_%2814676550274%29.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Kemmerer_Power_Station_under_construction_-_Nov_2024.jpg/1280px-Kemmerer_Power_Station_under_construction_-_Nov_2024.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/2/26/Overview_of_cooling_towers_of_Dukovany_Nuclear_Power_Station_near_Dukovany%2C_T%C5%99eb%C3%AD%C4%8D_District.jpg/1280px-Overview_of_cooling_towers_of_Dukovany_Nuclear_Power_Station_near_Dukovany%2C_T%C5%99eb%C3%AD%C4%8D_District.jpg"
]
out = {}
for u in U:
    time.sleep(5)
    for k in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
                out[u] = {"ok": True, "ct": r.headers.get("Content-Type"), "b64": base64.b64encode(r.read()).decode()}
            break
        except Exception as e:  # noqa: BLE001
            out[u] = {"ok": False, "err": f"{type(e).__name__}: {str(e)[:120]}"}; time.sleep(20)
Path("data/probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
