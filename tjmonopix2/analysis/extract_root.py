import ROOT
import pandas as pd
from argparse import ArgumentParser
import numpy as np

# usage python3 extract_root.py --start 297 --end 297 --path /home/yannik/vtx/testbeam/data/monopix2/test


selected_keys = {
"AnalysisDUT/Monopix2_0/local_residuals/residualsX":'RMS',
"AnalysisDUT/Monopix2_0/local_residuals/residualsX1pix":'RMS',
"AnalysisDUT/Monopix2_0/local_residuals/residualsX2pix":'RMS',
"AnalysisDUT/Monopix2_0/local_residuals/residualsX3pix":'RMS',
"AnalysisDUT/Monopix2_0/local_residuals/residualsY":'RMS',
"AnalysisDUT/Monopix2_0/local_residuals/residualsY1pix":'RMS',
"AnalysisDUT/Monopix2_0/local_residuals/residualsY2pix":'RMS',
"AnalysisDUT/Monopix2_0/local_residuals/residualsY3pix":'RMS',
"AnalysisDUT/Monopix2_0/clusterChargeAssociated":'Mean',
"AnalysisDUT/Monopix2_0/seedChargeAssociated":'Mean',
"AnalysisDUT/Monopix2_0/clusterSizeAssociated":'Mean',
"AnalysisDUT/Monopix2_0/clusterWidthRowAssociated":'Mean',
"AnalysisDUT/Monopix2_0/clusterWidthColAssociated":'Mean',
"AnalysisEfficiency/Monopix2_0/pixelEfficiencyMap_trackPos":'Efficiency',
"AnalysisEfficiency/Monopix2_0/chipEfficiencyMap_trackPos":'Efficiency',
"AnalysisEfficiency/Monopix2_0/distanceTrackHit2D":'RMS',
"AnalysisEfficiency/Monopix2_0/eTotalEfficiency":'single_Efficiency',
"AnalysisEfficiency/Monopix2_0/efficiencyColumns":'Efficiency',
"AnalysisEfficiency/Monopix2_0/efficiencyRows":'Efficiency'
}

def parse_args():
    """Parse command line arguments."""
    parser = ArgumentParser(description='Crawl root files')
    add_arg = parser.add_argument
    add_arg('-s', '--start', type=int, default=1, help='Start run')
    add_arg('-e', '--end', type=int, default=2, help='End run')
    add_arg('-p', '--path', type=str, default='', help='Path to root files')
    return parser.parse_args()


def get_object(path,runs):
    if not path.endswith('/'):
        path=path+'/'
    columns = [x.split('/')[-1] for x in selected_keys.keys()]
    df = pd.DataFrame(columns=columns, index=runs)

    root_files = ['analysis_run{}.root'.format(x) for x in runs]

    for i,file in enumerate(root_files):
        try:
            f = ROOT.TFile(path+file)
        except Exception:
            continue
        list_per_file = []
        for key in selected_keys.keys():
            plot = f.Get(key)
            #print(key)
            if selected_keys[key] == 'RMS' or selected_keys[key] == 'Mean':
                attr = getattr(plot,"Get%s" % selected_keys[key])
                val = attr()
                list_per_file.append(val)
                #print(val)
            elif selected_keys[key] == 'Efficiency':
                x_start = 150
                x_stop = 300
                y_start = 300
                y_stop = 400
                val_pixels = []
                for x in range(x_start,x_stop,1):
                    if x==225:
                        continue
                    for y in range(y_start,y_stop,1):
                        global_bin = plot.GetGlobalBin(x,y)
                        val_single_pixel = plot.GetEfficiency(global_bin)
                        if val_single_pixel>0.0001:
                            #if val_single_pixel>0.00001:
                            val_pixels.append(val_single_pixel)
                if(len(val_pixels)!=0):
                    list_per_file.append(sum(val_pixels)/len(val_pixels))
                else:
                    list_per_file.append(0)
            elif selected_keys[key] == 'single_Efficiency':
                global_bin = plot.GetGlobalBin(1,1)
                val_single_pixel = plot.GetEfficiency(global_bin)
                list_per_file.append(val_single_pixel)
        df.loc[runs[i]] = list_per_file
    return df


if __name__ == '__main__':

    args = parse_args()
    result_df = get_object(args.path,list(range(args.start,args.end+1)))
    
    result_df_res = pd.DataFrame()
    result_df_cluster = pd.DataFrame()
    result_df_eff = pd.DataFrame()

    result_df_res['residualsX'] = result_df['residualsX']
    result_df_res['residualsX1pix'] = result_df['residualsX1pix']
    result_df_res['residualsX2pix'] = result_df['residualsX2pix']
    result_df_res['residualsX3pix'] = result_df['residualsX3pix']
    result_df_res['residualsY'] = result_df['residualsY']
    result_df_res['residualsY1pix'] = result_df['residualsY1pix']
    result_df_res['residualsY2pix'] = result_df['residualsY2pix']
    result_df_res['residualsY3pix'] = result_df['residualsY3pix']

    result_df_cluster['clusterChargeAssociated'] = result_df['clusterChargeAssociated']
    result_df_cluster['seedChargeAssociated'] = result_df['seedChargeAssociated']
    result_df_cluster['clusterSizeAssociated'] = result_df['clusterSizeAssociated']
    result_df_cluster['clusterWidthRowAssociated'] = result_df['clusterWidthRowAssociated']
    result_df_cluster['clusterWidthColAssociated'] = result_df['clusterWidthColAssociated']

    result_df_eff['pixelEfficiencyMap_trackPos'] = result_df['pixelEfficiencyMap_trackPos']
    result_df_eff['chipEfficiencyMap_trackPos'] = result_df['chipEfficiencyMap_trackPos']
    result_df_eff['distanceTrackHit2D'] = result_df['distanceTrackHit2D']
    result_df_eff['eTotalEfficiency'] = result_df['eTotalEfficiency']
    result_df_eff['efficiencyColumns'] = result_df['efficiencyColumns']
    result_df_eff['efficiencyRows'] = result_df['efficiencyRows']

    print(result_df_res.to_markdown())
    print('\n')
    print(result_df_cluster.to_markdown())
    print('\n')
    print(result_df_eff.to_markdown())
    #print(tabulate(result_df, headers='keys', tablefmt='psql'))
    
    
    
    
    
    
    
    
    
    
    
    
    
    