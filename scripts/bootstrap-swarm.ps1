param(
    [Parameter(Mandatory = $true)]
    [ValidateCount(3, 3)]
    [string[]]$ManagerNodes
)

$ErrorActionPreference = 'Stop'

$managerCount = docker node ls --filter role=manager --format '{{.Hostname}}' 2>$null
if (-not $managerCount) {
    throw 'Run docker swarm init on the first manager and join the other two managers before applying labels.'
}

foreach ($node in $ManagerNodes) {
    $match = docker node inspect $node --format '{{.Description.Hostname}}' 2>$null
    if (-not $match) { throw "Swarm manager node not found: $node" }
}

docker node update --label-add edu.role.edge=true --label-add edu.role.app=true $ManagerNodes[0]
docker node update --label-add edu.role.worker=true --label-add edu.role.runtime=true $ManagerNodes[1]
docker node update --label-add edu.role.data=true --label-add edu.role.app=true $ManagerNodes[2]

Write-Output 'Swarm labels applied. Create external configs and secrets before deploying the stack.'

