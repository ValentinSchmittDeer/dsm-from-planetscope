# MULTI-VIEW-STEREO DSM FROM PLANETSCOPE SATELLITES
> COMPUTER VISION PROCESS WITH REDUNDANT FRAME-BASED SATELLITES    (14th Feb 2022)

> © Valentin Schmitt (University of Stuttgart, IfP), 2022 - Author and Proprietary    
> © Planet Labs Inc., 2022 - Proprietary
    
**Caution: the usage of that algorithm is regulated by coppyright**    
**It has been design on Ubuntu and some functions must operate in Planet IT environment**

**Author:** [Valentin Schmitt (Planet intern, University of Stuttgart, IfP)](mailto:schmitt.h.valentin@gmail.com)    
**Supervisor:** [Apl. Prof. Dr.-Ing. Norbert Haala (University of Stuttgart, IfP)](mailto:norbert.haala@ifp.uni-stuttgart.de)    
**Stakeholders:** [Kelsey J. (Planet)](mailto:kels@planet.com) [Matthias K. (Planet)](mailto:matthias.kolbe@planet.com)

## ABSTRACT
Since 2015, Planet Labs has operated Cubesat 3U satellites for Earth observation and remote sensing monitoring. The Planetscope constellation contains around 130 Doves which are frame based sensors and they reached the daily time resolution in 2018. The whole setting is close to airborne photogrammetric acquisitions that allow digital surface modelling computation with Structure from Motion pipelines. Unlike low flight, Doves perch on orbits around 475 km high with a small field view angle acquiring 24 km x 16 km scenes and thus they hold a weak intersection geometry at theground. Nevertheless, they provide a very large redundancy. This study aims to design an automated process chain for 3D reconstruction enhanced with information redundancy. Product knowledge of overall organisation, hardware and software description as well as internal process specification outlines first hassles and sets a coarse methodology forth. Former studies about Planetscope matching built object oriented methodology which returned promising results. However, this research focuses on an image oriented approach which is closer to low flight custom. The research part sets the whole chain up which is divided into scene block creation, bundle adjustment and reconstruction sections. From the entire Planetscope database, the scene selection retrieves the best ones and sets a working directory in. Then, the adjustment section presents the strength and weakness of incoming Dove’s location models and it figures out a correcting procedure making use of the SRTM only. The image matching provides stereo point clouds with a large redundancy and the reconstruction part ends with a multi-view stereo method merging elevations and returns a standard DSM and its computation accuracy. External data (SRTM) is only involved during the bundle adjustment and reconstruction results are compared to ground truth without further transformation. That assessment runs over test sites (Providence Mountain, Stuttgart and Mount Saint Helens) and the last part outlines process issues and summarises the achievable accuracy. The final accuracy reaches 8 m in vertical direction (2 pixels) along a 4 m horizontal grid. All in all, this research sets the basis of Planetscope reconstruction with image approach, even though some computation limits remain and it covers only the case of Dove-Classic. Hence, all process improvements and extension with following satellite generation shall again improve outcomes. Furthermore, the final algorithm is almost automatic and it can be implemented on Planet customer portal.

## Main documents
- [ThesisReport.pdf](./ThesisReport.pdf): full thesis report
- [dsm_from_planetscope_workflow.png](./dsm_from_planetscope_workflow.png): algorithm visual description
- [dsm_from_planetscope.py](./dsm_from_planetscope.py): main script (for the moment it only return the algorithm usage)
- [src](./src): source codes and libraries directories
