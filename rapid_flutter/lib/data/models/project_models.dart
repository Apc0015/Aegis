class ProjectInfo {
  final String projectId;
  final String projectName;
  final String collectionName;

  const ProjectInfo({
    required this.projectId,
    required this.projectName,
    required this.collectionName,
  });

  factory ProjectInfo.fromJson(Map<String, dynamic> j) => ProjectInfo(
    projectId: j['project_id'] as String,
    projectName: j['project_name'] as String,
    collectionName: j['collection_name'] as String,
  );
}
